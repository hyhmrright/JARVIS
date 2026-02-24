-- 03_user_settings.sql
-- 用户设置表：模型偏好、API Key（加密存储）、工具开关
CREATE TABLE IF NOT EXISTS user_settings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    model_provider  VARCHAR(50) NOT NULL DEFAULT 'deepseek',
    model_name      VARCHAR(100) NOT NULL DEFAULT 'deepseek-chat',
    api_keys        JSONB NOT NULL DEFAULT '{}',
    enabled_tools   JSONB NOT NULL DEFAULT '["search","code_exec","file","datetime"]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_settings_user_id UNIQUE (user_id)
);

COMMENT ON TABLE user_settings IS '用户设置表：每用户一行，存储模型偏好和 API Key';
COMMENT ON COLUMN user_settings.model_provider IS 'LLM 提供商标识：deepseek / openai / anthropic';
COMMENT ON COLUMN user_settings.model_name IS '模型名称：deepseek-chat / gpt-4 / claude-3 等';
COMMENT ON COLUMN user_settings.api_keys IS 'Fernet 加密后的 API Key JSON，格式 {"provider": "encrypted_key"}';
COMMENT ON COLUMN user_settings.enabled_tools IS '已启用工具列表 JSON 数组';

CREATE TRIGGER set_user_settings_updated_at
    BEFORE UPDATE ON user_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
