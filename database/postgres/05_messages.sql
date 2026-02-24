-- 05_messages.sql
-- 消息表：存储对话中的每条消息
CREATE TABLE IF NOT EXISTS messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role                VARCHAR(20) NOT NULL,
    content             TEXT NOT NULL,
    tool_calls          JSONB,
    model_provider      VARCHAR(50),
    model_name          VARCHAR(100),
    tokens_input        INTEGER,
    tokens_output       INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_messages_role CHECK (role IN ('human', 'ai', 'tool', 'system'))
);

COMMENT ON TABLE messages IS '消息表：存储对话中每条消息及 token 统计';
COMMENT ON COLUMN messages.role IS '角色：human（用户）/ ai（AI 回复）/ tool（工具结果）/ system（系统提示）';
COMMENT ON COLUMN messages.tool_calls IS '工具调用详情 JSON，仅 role=ai 时可能非空';
COMMENT ON COLUMN messages.tokens_input IS '输入 token 数，用于用量统计';
COMMENT ON COLUMN messages.tokens_output IS '输出 token 数，用于用量统计';
