"""Unit tests for round-table group chat parsing and prompt formatting."""

from backend.roundtable import parse_mentions, short_model_name, format_roundtable_prompt


def test_short_model_name():
    assert short_model_name("local/qwen3.6-27b@first-principles") == "qwen3.6-27b"
    assert short_model_name("thinkingmachines/inkling:free@red-team-reasoning") == "inkling"
    assert short_model_name("nvidia/nemotron-3-ultra-550b-a55b:free") == "nemotron-3-ultra-550b-a55b"
    assert short_model_name("anthropic/claude-3.5-sonnet") == "claude-3.5-sonnet"


def test_parse_mentions_broadcast_default():
    models = [
        "local/qwen3.6-27b@first-principles",
        "thinkingmachines/inkling:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free"
    ]
    # No @mention: broadcast to all
    targets, is_broadcast = parse_mentions("Selam beyler, nasılsınız?", models)
    assert is_broadcast is True
    assert targets == models


def test_parse_mentions_broadcast_explicit():
    models = [
        "local/qwen3.6-27b@first-principles",
        "thinkingmachines/inkling:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free"
    ]
    targets, is_broadcast = parse_mentions("@all sizce hangisi daha iyi?", models)
    assert is_broadcast is True
    assert targets == models

    targets2, is_broadcast2 = parse_mentions("@herkes ne düşünüyorsunuz?", models)
    assert is_broadcast2 is True
    assert targets2 == models


def test_parse_mentions_single_target():
    models = [
        "local/qwen3.6-27b@first-principles",
        "local/antigravity",
        "local/claude-code",
        "thinkingmachines/inkling:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free"
    ]
    # Tag specific model
    targets, is_broadcast = parse_mentions("@qwen sence bu mimari mantıklı mı?", models)
    assert is_broadcast is False
    assert targets == ["local/qwen3.6-27b@first-principles"]

    targets_ink, is_broadcast_ink = parse_mentions("@inkling sen ne dersin?", models)
    assert is_broadcast_ink is False
    assert targets_ink == ["thinkingmachines/inkling:free"]

    # Test alias @agy -> local/antigravity
    targets_agy, is_broadcast_agy = parse_mentions("@agy kod kalitesini kontrol et", models)
    assert is_broadcast_agy is False
    assert targets_agy == ["local/antigravity"]

    # Test alias @claude -> local/claude-code
    targets_claude, is_broadcast_claude = parse_mentions("@claude mimariyi açıkla", models)
    assert is_broadcast_claude is False
    assert targets_claude == ["local/claude-code"]


def test_format_roundtable_prompt():
    models = [
        "local/qwen3.6-27b",
        "thinkingmachines/inkling:free"
    ]
    history = [
        {"role": "user", "sender_name": "Ali", "content": "Selam!"},
        {"role": "assistant", "model": "local/qwen3.6-27b", "content": "Aleyküm selam Ali!"},
        {"role": "assistant", "model": "thinkingmachines/inkling:free", "content": "Merhabalar!"}
    ]

    # Build prompt for qwen
    messages = format_roundtable_prompt(
        current_model="local/qwen3.6-27b",
        all_models=models,
        history_messages=history,
        user_content="@qwen bana bir örnek ver",
        user_name="Ali"
    )

    # First message is system
    assert messages[0]["role"] == "system"
    assert "Ali" in messages[0]["content"]

    # In history, qwen's own message is 'assistant', inkling's message and the user prompt are normalized/merged
    assert messages[1] == {"role": "user", "content": "[Ali]: Selam!"}
    assert messages[2] == {"role": "assistant", "content": "Aleyküm selam Ali!"}
    assert messages[3] == {
        "role": "user",
        "content": "[inkling]: Merhabalar!\n\n[Ali]: @qwen bana bir örnek ver"
    }


def test_parse_peer_mentions():
    from backend.roundtable import parse_peer_mentions

    models = [
        "local/antigravity",
        "local/claude-code",
        "local/qwen3.6-27b",
        "liquid/lfm-2.5-2.6b:free"
    ]

    # Antigravity calls Qwen
    content = "@qwen3.6-27b selamlar. Ali pası bize attı; ekibe kısaca kendini bir tanıt istersen."
    peers = parse_peer_mentions(content, models, author_model="local/antigravity")
    assert peers == ["local/qwen3.6-27b"]

    # Short mention @qwen
    peers_short = parse_peer_mentions("Bence @qwen de bu konuda fikir vermeli.", models, author_model="local/antigravity")
    assert peers_short == ["local/qwen3.6-27b"]

    # Mention with alias @claude
    peers_claude = parse_peer_mentions("@claude sence mantıklı mı?", models, author_model="local/qwen3.6-27b")
    assert peers_claude == ["local/claude-code"]

    # Mention self should be ignored
    peers_self = parse_peer_mentions("@qwen3.6-27b ben zaten söyledim.", models, author_model="local/qwen3.6-27b")
    assert peers_self == []

    # Broadcast mentions like @all should be ignored to avoid cascade storms
    peers_all = parse_peer_mentions("Teşekkürler @all herkese iyi çalışmalar.", models, author_model="local/antigravity")
    assert peers_all == []

    # Gemini alias should match local/antigravity
    peers_gemini = parse_peer_mentions("@gemini mimari hakkında ne dersin?", models, author_model="local/qwen3.6-27b")
    assert peers_gemini == ["local/antigravity"]

    # Mentions ending with sentence punctuation should be matched cleanly
    peers_dot = parse_peer_mentions("Selam @antigravity. Sistemler hazır.", models, author_model="local/qwen3.6-27b")
    assert peers_dot == ["local/antigravity"]

    peers_colon = parse_peer_mentions("@qwen: inference motorun aktif mi?", models, author_model="local/antigravity")
    assert peers_colon == ["local/qwen3.6-27b"]

    peers_paren = parse_peer_mentions("Bunu (@claude) da onayladı.", models, author_model="local/qwen3.6-27b")
    assert peers_paren == ["local/claude-code"]


def test_parse_mentions_gemini_and_qwen_aliases():
    models = [
        "local/antigravity",
        "local/claude-code",
        "local/qwen3.6-27b",
    ]
    # @gemini -> local/antigravity
    targets_gemini, is_bc_gemini = parse_mentions("@gemini nasılsın?", models)
    assert is_bc_gemini is False
    assert targets_gemini == ["local/antigravity"]

    # @qwen -> local/qwen3.6-27b
    targets_qwen, is_bc_qwen = parse_mentions("@qwen selam", models)
    assert is_bc_qwen is False
    assert targets_qwen == ["local/qwen3.6-27b"]


def test_format_roundtable_prompt_anchored_sliding_window():
    models = ["local/antigravity", "local/qwen3.6-27b"]
    
    # Create a 15-message long conversation
    history = [{"role": "user", "sender_name": "Ali", "content": "Root question: Docker network architecture"}]
    for i in range(1, 15):
        m = "local/antigravity" if i % 2 == 1 else "local/qwen3.6-27b"
        history.append({"role": "assistant", "model": m, "content": f"Turn {i} reply"})

    # Format with max_history_turns = 6
    messages = format_roundtable_prompt(
        current_model="local/antigravity",
        all_models=models,
        history_messages=history,
        user_content="Current user turn",
        user_name="Ali",
        max_history_turns=6
    )

    # First is system message
    assert messages[0]["role"] == "system"

    # Next should be anchored root message
    assert "Root question: Docker network architecture" in messages[1]["content"]
    assert "Opening Topic" in messages[1]["content"]

    # In the recent window, turns 9-14 should be present, but turns 1-8 should be omitted
    full_prompt_text = " ".join(m["content"] for m in messages)
    assert "Turn 14 reply" in full_prompt_text
    assert "Turn 10 reply" in full_prompt_text
    assert "Turn 2 reply" not in full_prompt_text
    assert "Turn 3 reply" not in full_prompt_text


