"""Prompt-injection hygiene for UNTRUSTED text (retrieved docs, Canvas content, page context).

Defense in depth: (1) suspicious instruction-like lines are removed, (2) the rest is wrapped in tags the system prompt
declares as data-only, (3) the assistant has no write tools, so even a successful injection cannot change anything.
"""
import re

_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|prompts|rules)",
    r"disregard (all |any |the )?(previous|prior|above|earlier|your) ",
    r"(reveal|print|show|repeat) (your|the) (system|hidden|initial) (prompt|instructions)",
    r"you are now (a|an|in) ",
    r"new instructions?:",
    r"^\s*(system|assistant|developer)\s*:",
    r"<\|?(im_start|im_end|system|endoftext)\|?>",
    r"act as (if you (are|were)|a|an) ",
    r"do not (tell|inform) the (user|teacher)",
    r"(send|post|forward|exfiltrate) .{0,40}(to|at) https?://",
]
_RX = [re.compile(p, re.IGNORECASE) for p in _PATTERNS]
_TAG = re.compile(r"</?\s*(untrusted_[a-z_]+|evidence|system|instructions?)\s*>", re.IGNORECASE)


def sanitize(text: str) -> tuple[str, bool]:
    """Return (clean_text, flagged). Flagged lines are replaced with a neutral marker."""
    flagged = False
    out = []
    for line in (text or "").splitlines():
        if any(r.search(line) for r in _RX):
            flagged = True
            out.append("[line removed: looked like an instruction]")
        else:
            out.append(_TAG.sub("", line))
    return "\n".join(out), flagged


def wrap(kind: str, text: str) -> str:
    clean, _ = sanitize(text)
    return f"<untrusted_{kind}>\n{clean}\n</untrusted_{kind}>"
