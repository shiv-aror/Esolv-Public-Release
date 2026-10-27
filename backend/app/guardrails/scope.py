"""Cheap deterministic checks run before/after the model (the model itself is also instructed to stay in scope)."""
import re

_GREETING = re.compile(r"^\s*(hi|hello|hey|thanks|thank you|good (morning|afternoon|evening)|yo)\W*\s*$", re.IGNORECASE)
_COMPLIANCE = re.compile(
    r"\b(eligib|exit|reclassif|placement|screener|identif|deadline|timeline|legal|iep|504|monitor|accountab|notification|"
    r"waiver|opt[- ]?out|compliance|required|must|mandat)", re.IGNORECASE)
_HARM = re.compile(r"\b(self[- ]harm|suicide|kill myself|abuse|abused|molest)", re.IGNORECASE)

GREETING_REPLY = ("Hi! I'm Esolv. Ask me about MCPS ELD paperwork, accountability requirements, accommodations, or "
                  "instructional materials, or ask me to look something up in your Canvas courses.")
NOT_FOUND_REPLY = ("I couldn't find this in the MCPS materials I have access to, so I won't guess. "
                   "Try rephrasing, or check with your school's ESOL coordinator.")
SAFETY_REPLY = ("If a student may be in danger or at risk of harm, follow your school's reporting procedure right away "
                "and contact your counselor or administrator. I can help find the MCPS procedure, but I can't handle emergencies.")
COORDINATOR_NOTE = "\n\n_This is guidance from the sources above, not a final determination. Confirm with your ESOL coordinator before acting._"


def is_greeting(text: str) -> bool:
    return bool(_GREETING.match(text or ""))


def needs_coordinator_note(question: str, answer: str = "") -> bool:
    return bool(_COMPLIANCE.search(question or ""))


def is_safety_concern(text: str) -> bool:
    return bool(_HARM.search(text or ""))
