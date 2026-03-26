"""Text chunker with CJK-aware splitting."""

_WORD_CHUNK_SIZE = 500
_WORD_OVERLAP = 50
_CJK_CHUNK_SIZE = 500  # characters
_CJK_OVERLAP = 50
_CJK_THRESHOLD = 0.3


def _cjk_ratio(text: str) -> float:
    """Calculate the ratio of CJK characters in text."""
    if not text:
        return 0.0
    cjk_count = sum(
        1
        for c in text
        if "\u4e00" <= c <= "\u9fff"
        or "\u3040" <= c <= "\u30ff"
        or "\uac00" <= c <= "\ud7af"  # Korean Hangul syllables
    )
    return cjk_count / len(text)


def _chunk_by_chars(text: str, size: int, overlap: int) -> list[str]:
    """Split text into overlapping character-based chunks."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return [c for c in chunks if c.strip()]


def _chunk_by_words(text: str, size: int, overlap: int) -> list[str]:
    """Split text into overlapping word-based chunks."""
    words = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start + size
        chunks.append(" ".join(words[start:end]))
        start += size - overlap
    return [c for c in chunks if c.strip()]


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks with CJK awareness.

    Uses character-based splitting for CJK-heavy text (>30% CJK characters)
    and word-based splitting for Latin/mixed text.

    Args:
        text: The text to chunk.
        chunk_size: Size parameter (word count for Latin, character count for CJK).
        overlap: Overlap parameter (word count for Latin, character count for CJK).

    Returns:
        List of non-empty text chunks.
    """
    if not text:
        return []
    if _cjk_ratio(text) > _CJK_THRESHOLD:
        return _chunk_by_chars(text, _CJK_CHUNK_SIZE, _CJK_OVERLAP)
    return _chunk_by_words(text, chunk_size, overlap)
