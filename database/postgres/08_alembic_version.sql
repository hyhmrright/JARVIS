-- 08_alembic_version.sql
-- 标记 alembic 迁移版本，与 backend/alembic/versions/ 保持同步。
-- 当 postgres 使用初始化脚本建表时，直接将版本设为当前 head，
-- 避免 alembic upgrade head 重复执行已由初始化脚本完成的 DDL。
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- 与最新迁移文件保持同步：002_add_persona_override.py
INSERT INTO alembic_version (version_num) VALUES ('002')
    ON CONFLICT DO NOTHING;
