"""Database models package.

Re-exports all model classes so that existing ``from app.db.models import X``
imports continue to work without modification.
"""

# Import all submodules first so SQLAlchemy's mapper registry has every class
# before any relationship string annotations are resolved.
from app.db.models.conversation import (
    AgentSession,
    Conversation,
    ConversationFolder,
    ConversationTag,
    Message,
    SharedConversation,
)
from app.db.models.document import Document
from app.db.models.misc import (
    AuditLog,
    Notification,
    Persona,
    UserMemory,
    Workflow,
    WorkflowRun,
)
from app.db.models.organization import (
    Invitation,
    Organization,
    Workspace,
    WorkspaceMember,
    WorkspaceSettings,
)
from app.db.models.plugin import InstalledPlugin, PluginConfig
from app.db.models.scheduler import (
    CronJob,
    JobExecution,
    Webhook,
    WebhookDeadLetter,
    WebhookDelivery,
)
from app.db.models.user import ApiKey, RefreshToken, User, UserRole, UserSettings

__all__ = [
    # user
    "UserRole",
    "User",
    "UserSettings",
    "ApiKey",
    "RefreshToken",
    # conversation
    "Conversation",
    "ConversationTag",
    "ConversationFolder",
    "AgentSession",
    "Message",
    "SharedConversation",
    # document
    "Document",
    # scheduler
    "CronJob",
    "JobExecution",
    "Webhook",
    "WebhookDelivery",
    "WebhookDeadLetter",
    # organization
    "Organization",
    "Workspace",
    "WorkspaceMember",
    "WorkspaceSettings",
    "Invitation",
    # plugin
    "PluginConfig",
    "InstalledPlugin",
    # misc
    "UserMemory",
    "AuditLog",
    "Notification",
    "Persona",
    "Workflow",
    "WorkflowRun",
]
