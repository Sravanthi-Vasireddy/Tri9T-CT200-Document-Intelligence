import re
import unicodedata
from typing import Dict

# Exact mapping for Unicode ligatures and special hyphens
LIGATURE_MAP: Dict[str, str] = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "ft",
    "\ufb06": "st",
    "\u2011": "-",   # Non-breaking hyphen -> standard hyphen
    "\u00ad": "",    # Soft hyphen -> empty
    "\u200b": "",    # Zero-width space -> empty
    "\u201c": '"',   # Left double quotation mark -> standard quote
    "\u201d": '"',   # Right double quotation mark -> standard quote
    "\u2018": "'",   # Left single quotation mark -> apostrophe
    "\u2019": "'",   # Right single quotation mark -> apostrophe
}

def normalize_text(text: str) -> str:
    """
    Carefully normalizes Unicode ligatures, quotes, and non-breaking hyphens
    while preserving meaningful symbols (e.g., '±', '≥', '≤', '–', '—', '%', numbers).
    """
    if not text:
        return ""
    
    # 1. Replace explicit ligatures and special hyphens
    for char, replacement in LIGATURE_MAP.items():
        if char in text:
            text = text.replace(char, replacement)
            
    # 2. Normalize whitespace (collapse multiple horizontal spaces, strip trailing/leading spaces on lines)
    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
            
    return "\n".join(lines)


def normalize_for_hashing(text: str) -> str:
    """
    Generates a deterministic string representation for content hashing.
    Normalizes whitespace and standardizes line breaks.
    """
    norm = normalize_text(text)
    # Collapse all whitespace sequences into a single space for cross-line uniformity
    return re.sub(r"\s+", " ", norm).strip().lower()
