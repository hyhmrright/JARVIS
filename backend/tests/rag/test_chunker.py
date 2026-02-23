from app.rag.chunker import chunk_text


def test_chunk_text_basic():
    text = "word " * 1000
    chunks = chunk_text(text, chunk_size=200, overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 250 for c in chunks)


def test_chunk_preserves_content():
    text = "Hello world. " * 100
    chunks = chunk_text(text)
    combined = " ".join(chunks)
    assert "Hello world" in combined
