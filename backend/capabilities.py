"""What a model can take as input.

Only vision for now. There is no reliable machine-readable source for custom or local endpoints,
so unknown models are treated as text-only: a missing image note is harmless, an image sent to a
model that rejects it fails the whole turn for that seat.

Order of precedence: explicit flag on the local-model / custom-provider record (`vision`),
then the VISION_MODELS env list (exact ids, comma separated), then the name patterns below.
"""

import os
import re

_VISION_PATTERNS = [
    r"^openai/(gpt-4o|gpt-4\.1|gpt-4-turbo|gpt-5|o1|o3|o4)",
    r"^anthropic/claude-(?!2|instant)",
    r"^(google/)?gemini",
    r"^x-ai/grok-(4|.*vision)",
    r"^meta-llama/llama-4",
    r"(^|[-_/])(vl|vision|llava|pixtral|minicpm-v|internvl|molmo)([-_/.:]|$)",
]
_VISION_RE = [re.compile(p) for p in _VISION_PATTERNS]


def _flag(record) -> "bool | None":
    if isinstance(record, dict) and "vision" in record:
        return bool(record["vision"])
    return None


def supports_vision(model: str) -> bool:
    base = (model or "").split("@")[0]

    from .config import LOCAL_MODELS

    record = LOCAL_MODELS.get(base)
    if record is None:
        try:
            from . import providers

            record = providers.get_provider_by_id(base)
        except Exception:
            record = None
    flag = _flag(record)
    if flag is not None:
        return flag

    extra = {m.strip() for m in os.getenv("VISION_MODELS", "").split(",") if m.strip()}
    if base in extra:
        return True
    # A custom endpoint's id ("custom/gemini-3-6-flash") says nothing about the model behind it,
    # so the upstream model id gets the same pattern check.
    names = [base]
    if isinstance(record, dict) and record.get("model_id"):
        names.append(str(record["model_id"]))
    return any(p.search(n.lower()) for n in names for p in _VISION_RE)
