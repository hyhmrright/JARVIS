-- 01_extensions.sql
-- PostgreSQL 扩展和公共函数
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 自动更新 updated_at 列的触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
