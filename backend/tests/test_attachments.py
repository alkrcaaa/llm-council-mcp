"""Attachments: content sniffing, image re-encoding, size/count limits, per-conversation storage."""

import io
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import attachments
from backend.main import app

client = TestClient(app)


@pytest.fixture
def conv():
    cid = client.post("/api/conversations", json={}).json()["id"]
    yield cid
    client.delete(f"/api/conversations/{cid}")


def _png(size=(8, 8)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, "red").save(buf, "PNG")
    return buf.getvalue()


def _jpeg_with_exif() -> bytes:
    img = Image.new("RGB", (40, 20), "blue")
    exif = Image.Exif()
    exif[0x010F] = "SecretCamera"  # Make
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def _pdf(text="hello pdf world") -> bytes:
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref)
    return out


def _upload(cid, name, data):
    return client.post(f"/api/conversations/{cid}/attachments", files={"file": (name, data)})


def test_image_roundtrip_and_listing(conv):
    r = _upload(conv, "pic.png", _png())
    assert r.status_code == 200, r.text
    meta = r.json()
    assert meta["kind"] == "image" and meta["mime"] == "image/png" and (meta["width"], meta["height"]) == (8, 8)
    assert "text" not in meta and "ext" not in meta

    got = client.get(f"/api/conversations/{conv}/attachments/{meta['id']}")
    assert got.status_code == 200 and got.headers["content-type"] == "image/png"
    assert got.headers["x-content-type-options"] == "nosniff"
    assert Image.open(io.BytesIO(got.content)).size == (8, 8)

    assert [m["id"] for m in client.get(f"/api/conversations/{conv}/attachments").json()] == [meta["id"]]


def test_type_comes_from_content_not_filename_or_header(conv):
    r = client.post(
        f"/api/conversations/{conv}/attachments",
        files={"file": ("photo.png", b"MZ\x90\x00\x03\x00\x00\x00binary", "image/png")},
    )
    assert r.status_code == 415
    assert _upload(conv, "x.exe", b"\x7fELF\x02\x01\x01\x00").status_code == 415
    assert _upload(conv, "empty.txt", b"").status_code == 400


def test_html_and_svg_are_served_as_plain_text_never_markup(conv):
    meta = _upload(conv, "a.svg", b"<svg onload=alert(1)></svg>").json()
    assert meta["kind"] == "text" and meta["mime"] == "text/plain"
    got = client.get(f"/api/conversations/{conv}/attachments/{meta['id']}")
    assert got.headers["content-type"].startswith("text/plain")
    assert got.headers["content-security-policy"] == "sandbox"


def test_exif_is_stripped_by_reencoding(conv):
    src = _jpeg_with_exif()
    assert b"SecretCamera" in src
    meta = _upload(conv, "cam.jpg", src).json()
    body = client.get(f"/api/conversations/{conv}/attachments/{meta['id']}").content
    assert b"SecretCamera" not in body and not Image.open(io.BytesIO(body)).getexif()


def test_payload_appended_to_image_is_dropped(conv):
    meta = _upload(conv, "p.png", _png() + b"<?php system($_GET[0]); ?>").json()
    assert b"<?php" not in client.get(f"/api/conversations/{conv}/attachments/{meta['id']}").content


def test_large_image_is_downscaled(conv):
    meta = _upload(conv, "big.png", _png((4000, 100))).json()
    assert meta["width"] == attachments.MAX_IMAGE_SIDE


def test_corrupt_image_and_pixel_bomb_are_refused(conv):
    assert _upload(conv, "bad.png", _png()[:40]).status_code == 400
    assert _upload(conv, "bad.png", b"\x89PNG\r\n\x1a\n" + b"junk" * 20).status_code == 400
    bomb = _png((10, 10))
    # Patch the IHDR width/height to 60000x60000 without data: must be refused before decode.
    ihdr = bytearray(bomb)
    ihdr[16:24] = (60000).to_bytes(4, "big") * 2
    assert _upload(conv, "bomb.png", bytes(ihdr)).status_code in (400, 413)


def test_pdf_text_is_extracted_and_kept_server_side(conv):
    meta = _upload(conv, "doc.pdf", _pdf()).json()
    assert meta["kind"] == "pdf" and meta["text_chars"] > 0
    stored = attachments.get_meta(conv, meta["id"])
    assert "hello pdf world" in stored["text"]


def test_garbage_pdf_is_refused(conv):
    assert _upload(conv, "x.pdf", b"%PDF-1.4 this is not a pdf").status_code == 400


def test_text_file_limits_and_truncation(conv):
    assert _upload(conv, "big.txt", b"a" * (attachments.MAX_BYTES["text"] + 1)).status_code == 413
    text = ("x" * (attachments.MAX_EXTRACT_CHARS + 10)).encode()
    meta = _upload(conv, "long.txt", text).json()
    assert meta["truncated"] is True and meta["text_chars"] == attachments.MAX_EXTRACT_CHARS


def test_filename_is_sanitised_and_not_used_as_a_path(conv):
    meta = _upload(conv, "../../etc/passwd.txt", b"hi").json()
    assert meta["name"] == "passwd.txt"
    path, _ = attachments.file_path(conv, meta["id"]) or ("", {})
    assert os.path.realpath(path).startswith(os.path.realpath(attachments.ATTACHMENTS_DIR))
    assert "passwd" not in os.path.basename(path)


def test_attachment_limit_per_conversation(conv, monkeypatch):
    monkeypatch.setattr(attachments, "MAX_PER_CONVERSATION", 2)
    assert _upload(conv, "1.txt", b"1").status_code == 200
    assert _upload(conv, "2.txt", b"2").status_code == 200
    assert _upload(conv, "3.txt", b"3").status_code == 409


def test_unknown_conversation_and_bad_ids(conv):
    assert _upload("does-not-exist", "a.txt", b"hi").status_code == 404
    assert client.get(f"/api/conversations/{conv}/attachments/not-an-id").status_code == 404
    assert client.get(f"/api/conversations/{conv}/attachments/{'0' * 32}").status_code == 404
    assert client.get("/api/conversations/..%2F..%2Fx/attachments/" + "0" * 32).status_code == 404


def test_attachment_is_not_reachable_through_another_conversation(conv):
    other = client.post("/api/conversations", json={}).json()["id"]
    try:
        meta = _upload(conv, "a.txt", b"private").json()
        assert client.get(f"/api/conversations/{other}/attachments/{meta['id']}").status_code == 404
    finally:
        client.delete(f"/api/conversations/{other}")


def test_delete_one_and_conversation_cleanup():
    cid = client.post("/api/conversations", json={}).json()["id"]
    a = _upload(cid, "a.txt", b"a").json()["id"]
    _upload(cid, "b.txt", b"b")
    assert client.delete(f"/api/conversations/{cid}/attachments/{a}").status_code == 200
    assert client.delete(f"/api/conversations/{cid}/attachments/{a}").status_code == 404
    assert len(client.get(f"/api/conversations/{cid}/attachments").json()) == 1

    folder = os.path.join(attachments.ATTACHMENTS_DIR, cid)
    assert os.path.isdir(folder)
    client.delete(f"/api/conversations/{cid}")
    assert not os.path.exists(folder)


def test_upload_body_cap_is_larger_than_the_global_one_but_still_bounded():
    from backend import limits

    assert limits.MAX_UPLOAD_BYTES > limits.MAX_BODY_BYTES
    assert limits._UPLOAD.match("/api/conversations/abc/attachments")
    assert not limits._UPLOAD.match("/api/conversations/abc/message")
    assert limits.is_costly("POST", "/api/conversations/abc/attachments")
