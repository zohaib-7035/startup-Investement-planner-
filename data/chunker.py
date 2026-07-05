import re
from typing import List, Dict

# Ordered so that longer item codes (1A, 1B, 7A, 9A) are matched before their numeric prefix
_SECTION_PATTERNS = [
    (re.compile(r"\bITEM\s+1A[\s\.\:\-]", re.IGNORECASE), "Risk Factors"),
    (re.compile(r"\bITEM\s+1B[\s\.\:\-]", re.IGNORECASE), "Unresolved Staff Comments"),
    (re.compile(r"\bITEM\s+1[\s\.\:\-]", re.IGNORECASE), "Business"),
    (re.compile(r"\bITEM\s+2[\s\.\:\-]", re.IGNORECASE), "Properties"),
    (re.compile(r"\bITEM\s+3[\s\.\:\-]", re.IGNORECASE), "Legal Proceedings"),
    (re.compile(r"\bITEM\s+7A[\s\.\:\-]", re.IGNORECASE), "Quantitative Disclosures"),
    (re.compile(r"\bITEM\s+7[\s\.\:\-]", re.IGNORECASE), "MD&A"),
    (re.compile(r"\bITEM\s+8[\s\.\:\-]", re.IGNORECASE), "Financial Statements"),
    (re.compile(r"\bITEM\s+9A[\s\.\:\-]", re.IGNORECASE), "Controls and Procedures"),
    (re.compile(r"\bITEM\s+9[\s\.\:\-]", re.IGNORECASE), "Changes in Accountants"),
]


def _split_by_paragraphs(text: str, max_chars: int) -> List[str]:
    if len(text) <= max_chars:
        return [text]
    paragraphs = text.split("\n\n")
    result = []
    current = ""
    for para in paragraphs:
        stripped = para.strip()
        if not stripped:
            continue
        if not current:
            current = stripped
        elif len(current) + 2 + len(stripped) <= max_chars:
            current = current + "\n\n" + stripped
        else:
            result.append(current)
            # Single paragraph longer than max_chars is kept as-is per contract
            current = stripped
    if current:
        result.append(current)
    return result if result else [text]


def chunk_filing(text: str, max_chars: int = 4000) -> List[Dict]:
    try:
        if not text:
            return []

        boundaries: List[tuple] = []
        for pattern, section_name in _SECTION_PATTERNS:
            for m in pattern.finditer(text):
                boundaries.append((m.start(), section_name))

        boundaries.sort(key=lambda x: x[0])

        chunks: List[Dict] = []
        chunk_id = 1

        def _emit(content: str, name: str) -> None:
            nonlocal chunk_id
            for sub in _split_by_paragraphs(content, max_chars):
                if sub:
                    chunks.append({
                        "chunk_id": chunk_id,
                        "section_name": name,
                        "content": sub,
                        "char_count": len(sub),
                    })
                    chunk_id += 1

        if not boundaries:
            _emit(text.strip(), "General")
            return chunks

        if boundaries[0][0] > 0:
            preamble = text[: boundaries[0][0]].strip()
            if preamble:
                _emit(preamble, "Preamble")

        for i, (pos, section_name) in enumerate(boundaries):
            next_pos = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
            section_text = text[pos:next_pos].strip()
            if section_text:
                _emit(section_text, section_name)

        return chunks
    except Exception:
        return []
