-- 06_documents.sql
-- 文档表：用户上传的知识库文档元数据
CREATE TABLE IF NOT EXISTS documents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename            VARCHAR(255) NOT NULL,
    file_type           VARCHAR(20) NOT NULL,
    file_size_bytes     BIGINT NOT NULL,
    chunk_count         INTEGER NOT NULL DEFAULT 0,
    qdrant_collection   VARCHAR(255) NOT NULL,
    minio_object_key    VARCHAR(500) NOT NULL,
    is_deleted          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_documents_file_type CHECK (file_type IN ('pdf', 'txt', 'md', 'docx'))
);

COMMENT ON TABLE documents IS '文档表：用户上传的知识库文档元数据';
COMMENT ON COLUMN documents.qdrant_collection IS 'Qdrant 中对应的 Collection 名称，格式 user_{user_id}';
COMMENT ON COLUMN documents.minio_object_key IS 'MinIO 中的对象路径，格式 {user_id}/{uuid}_{filename}';
COMMENT ON COLUMN documents.is_deleted IS '软删除标记';
COMMENT ON COLUMN documents.chunk_count IS '文档切片数量，向量化后回填';
