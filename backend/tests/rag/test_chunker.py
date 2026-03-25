"""Tests for CJK-aware RAG text chunker."""

from app.rag.chunker import chunk_text


def test_chunk_text_basic():
    text = "word " * 1000
    chunks = chunk_text(text, chunk_size=200, overlap=20)
    assert len(chunks) > 1
    # 用词数（word count）而非字符数断言，与 chunk_text 的 chunk_size 语义一致
    assert all(len(c.split()) <= 200 for c in chunks)


def test_chunk_preserves_content():
    text = "Hello world. " * 100
    chunks = chunk_text(text)
    combined = " ".join(chunks)
    assert "Hello world" in combined


def test_cjk_text_char_split():
    """Test that CJK-heavy text uses character-based splitting."""
    text = "这是一段中文文字。" * 300  # long CJK text (>30% CJK)
    chunks = chunk_text(text)
    assert len(chunks) > 0
    for chunk in chunks:
        assert len(chunk) <= 600  # _CJK_CHUNK_SIZE + some buffer for boundary


def test_mixed_text_favors_cjk_split():
    """Test that text with >30% CJK uses character-based splitting."""
    cjk_part = "中文内容" * 50
    latin_part = "english " * 30
    text = cjk_part + latin_part  # CJK >> 30%
    chunks = chunk_text(text)
    assert len(chunks) > 0


def test_mostly_latin_with_some_cjk_uses_word_path():
    """Test that mostly-Latin text with some CJK uses word-based splitting."""
    latin = "word " * 200
    cjk = "中文" * 10
    text = latin + cjk  # CJK << 30%
    chunks = chunk_text(text)
    assert len(chunks) > 0
    # Verify word-based splitting (chunks should have space separators)
    for chunk in chunks:
        if chunk != chunks[-1]:  # Last chunk might be short
            assert len(chunk.split()) > 1


def test_empty_text_returns_empty():
    """Test that empty text returns empty list."""
    assert chunk_text("") == []


def test_short_text_single_chunk():
    """Test that short text returns single chunk."""
    text = "short text"
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0] == "short text"


def test_english_text_word_split():
    """Test that English text is split by words."""
    text = "hello world " * 600  # 1200 words total
    chunks = chunk_text(text)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.split()) <= 600  # _WORD_CHUNK_SIZE


def test_japanese_text_char_split():
    """Test that Japanese text uses character-based splitting."""
    text = "これは日本語のテキストです。" * 300
    chunks = chunk_text(text)
    assert len(chunks) > 0


def test_korean_text_char_split():
    """Test that Korean text uses character-based splitting."""
    text = "이것은 한국어 텍스트입니다." * 300
    chunks = chunk_text(text)
    assert len(chunks) > 0
