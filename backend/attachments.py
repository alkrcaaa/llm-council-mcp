"""Chat attachments: validated, re-encoded and stored per conversation.

Nothing the client says about a file is trusted: the type comes from magic bytes, images are
decoded and re-encoded (drops EXIF/GPS and any appended payload), and the stored name is ours.
"""

import io
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .config import DATA_ROOT

ATTACHMENTS_DIR = os.path.join(DATA_ROOT, "attachments")

MAX_BYTES = {"image": 10_000_000, "pdf": 20_000_000, "text": 1_000_000}
MAX_PER_CONVERSATION = 20
MAX_IMAGE_SIDE = 2048
MAX_IMAGE_PIXELS = 50_000_000
MAX_EXTRACT_CHARS = 50_000
MAX_PDF_PAGES = 200

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ATT_ID = re.compile(r"^[0-9a-f]{32}$")


class AttachmentError(ValueError):
    """The upload was refused; the message is safe to show to the user."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def sniff(data: bytes) -> Tuple[str, str]:
    """Return (kind, mime) from the content itself, or raise AttachmentError."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image", "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image", "image/webp"
    if data.startswith(b"%PDF-"):
        return "pdf", "application/pdf"
    if b"\x00" not in data:
        try:
            data.decode("utf-8-sig")
            return "text", "text/plain"
        except UnicodeDecodeError:
            pass
    raise AttachmentError("Unsupported file type. Allowed: PNG, JPEG, GIF, WebP, PDF, UTF-8 text.", 415)


def _clean_name(name: Optional[str]) -> str:
    base = os.path.basename((name or "").replace("\\", "/"))
    base = re.sub(r"[\x00-\x1f\x7f]", "", base).strip()
    return base[:120] or "file"


def _reencode_image(data: bytes) -> Tuple[bytes, str, str, int, int]:
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        img = Image.open(io.BytesIO(data))
        if img.width * img.height > MAX_IMAGE_PIXELS:
            raise AttachmentError("Image dimensions are too large.", 413)
        img.load()
    except AttachmentError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError, ValueError):
        raise AttachmentError("The image could not be decoded.")

    img = ImageOps.exif_transpose(img) or img  # bake in rotation before the metadata is dropped
    img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    out = io.BytesIO()
    if (img.format or "").upper() == "JPEG" or data.startswith(b"\xff\xd8\xff"):
        img.convert("RGB").save(out, "JPEG", quality=88, optimize=True)
        mime, ext = "image/jpeg", "jpg"
    else:  # GIF keeps its first frame only
        img.convert("RGBA" if "A" in img.getbands() or img.mode == "P" else "RGB").save(out, "PNG", optimize=True)
        mime, ext = "image/png", "png"
    return out.getvalue(), mime, ext, img.width, img.height


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise AttachmentError("Encrypted PDFs are not supported.")
        parts, total = [], 0
        for page in reader.pages[:MAX_PDF_PAGES]:
            text = page.extract_text() or ""
            parts.append(text)
            total += len(text)
            if total > MAX_EXTRACT_CHARS:
                break
        return "\n\n".join(parts)
    except AttachmentError:
        raise
    except Exception:
        raise AttachmentError("The PDF could not be read.")


def _conv_dir(conversation_id: str) -> str:
    if not _ID.match(conversation_id or ""):
        raise AttachmentError("Invalid conversation id.", 404)
    return os.path.join(ATTACHMENTS_DIR, conversation_id)


def _atomic_write(path: str, data: bytes) -> None:
    tmp = f"{path}.{uuid.uuid4().hex}.tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def save(conversation_id: str, filename: Optional[str], data: bytes) -> Dict[str, Any]:
    """Validate and store one upload. Returns the public metadata (no extracted text)."""
    if not data:
        raise AttachmentError("The file is empty.")
    kind, mime = sniff(data)
    if len(data) > MAX_BYTES[kind]:
        raise AttachmentError(f"File too large for a {kind} (limit {MAX_BYTES[kind] // 1_000_000} MB).", 413)

    folder = _conv_dir(conversation_id)
    if len(list_for(conversation_id)) >= MAX_PER_CONVERSATION:
        raise AttachmentError(f"At most {MAX_PER_CONVERSATION} attachments per conversation.", 409)

    meta: Dict[str, Any] = {"kind": kind, "name": _clean_name(filename)}
    if kind == "image":
        stored, mime, ext, meta["width"], meta["height"] = _reencode_image(data)
    elif kind == "pdf":
        stored, ext = data, "pdf"
        text = _extract_pdf(data)
        meta["text"], meta["truncated"] = text[:MAX_EXTRACT_CHARS], len(text) > MAX_EXTRACT_CHARS
    else:
        stored, ext = data, "txt"
        text = data.decode("utf-8-sig")
        meta["text"], meta["truncated"] = text[:MAX_EXTRACT_CHARS], len(text) > MAX_EXTRACT_CHARS

    att_id = uuid.uuid4().hex
    meta.update(
        id=att_id,
        mime=mime,
        ext=ext,
        size=len(stored),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    os.makedirs(folder, mode=0o700, exist_ok=True)
    _atomic_write(os.path.join(folder, f"{att_id}.{ext}"), stored)
    _atomic_write(os.path.join(folder, f"{att_id}.json"), json.dumps(meta).encode())
    return public(meta)


def public(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Metadata safe for the client: extracted text stays server-side."""
    out = {k: v for k, v in meta.items() if k not in ("text", "ext")}
    if "text" in meta:
        out["text_chars"] = len(meta["text"])
    return out


def get_meta(conversation_id: str, att_id: str) -> Optional[Dict[str, Any]]:
    if not _ATT_ID.match(att_id or ""):
        return None
    try:
        with open(os.path.join(_conv_dir(conversation_id), f"{att_id}.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, AttachmentError):
        return None


def file_path(conversation_id: str, att_id: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    meta = get_meta(conversation_id, att_id)
    if not meta:
        return None
    path = os.path.join(_conv_dir(conversation_id), f"{att_id}.{meta['ext']}")
    return (path, meta) if os.path.isfile(path) else None


def list_for(conversation_id: str) -> List[Dict[str, Any]]:
    try:
        folder = _conv_dir(conversation_id)
        names = [n for n in os.listdir(folder) if n.endswith(".json")]
    except (OSError, AttachmentError):
        return []
    metas = [m for m in (get_meta(conversation_id, n[:-5]) for n in names) if m]
    return sorted(metas, key=lambda m: m.get("created_at", ""))


def delete(conversation_id: str, att_id: str) -> bool:
    found = file_path(conversation_id, att_id)
    if not found:
        return False
    path, _ = found
    for p in (path, os.path.join(_conv_dir(conversation_id), f"{att_id}.json")):
        try:
            os.remove(p)
        except OSError:
            pass
    return True


def delete_conversation_attachments(conversation_id: str) -> None:
    try:
        shutil.rmtree(_conv_dir(conversation_id), ignore_errors=True)
    except AttachmentError:
        pass
