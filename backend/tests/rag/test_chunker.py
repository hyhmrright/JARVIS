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
