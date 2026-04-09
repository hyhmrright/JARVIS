from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.canvas import router as canvas_router
from app.api.chat.routes import router as chat_router
from app.api.chat_files import router as chat_files_router
from app.api.conversations import router as conversations_router
from app.api.cron import router as cron_router
from app.api.documents import router as documents_router
from app.api.export import router as export_router
from app.api.folders import router as folders_router
from app.api.gateway import router as gateway_router
from app.api.invitations import router as invitations_router
from app.api.keys import router as keys_router
from app.api.logs import router as logs_router
from app.api.memory import router as memory_router
from app.api.notifications import router as notifications_router
from app.api.organizations import router as organizations_router
from app.api.personas import router as personas_router
from app.api.plugins import router as plugins_router
from app.api.public import router as public_router
from app.api.search import router as search_router
from app.api.settings import router as settings_router
from app.api.tts import router as tts_router
from app.api.usage import router as usage_router
from app.api.voice import router as voice_router
from app.api.webhooks import router as webhooks_router
from app.api.workflows import router as workflows_router
from app.api.workspaces import router as workspaces_router

api_router = APIRouter()

# 聚合所有业务路由
routers = [
    auth_router,
    admin_router,
    canvas_router,
    chat_router,
    chat_files_router,
    conversations_router,
    folders_router,
    notifications_router,
    cron_router,
    documents_router,
    settings_router,
    logs_router,
    memory_router,
    search_router,
    plugins_router,
    personas_router,
    public_router,
    gateway_router,
    tts_router,
    voice_router,
    usage_router,
    webhooks_router,
    workflows_router,
    keys_router,
    organizations_router,
    workspaces_router,
    invitations_router,
    export_router,
]

for router in routers:
    api_router.include_router(router)
