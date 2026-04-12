# backend/tests/db/test_conversation_model.py
"""Unit tests for Conversation domain methods — no DB connection needed."""

import uuid

from app.db.models import Conversation, Message


def test_conversation_create_sets_required_fields():
    user_id = uuid.uuid4()
    conv = Conversation.create(user_id=user_id, title="My Chat")
    assert conv.user_id == user_id
    assert conv.title == "My Chat"
    assert conv.id is not None


def test_conversation_create_default_title():
    conv = Conversation.create(user_id=uuid.uuid4())
    assert conv.title == "New Conversation"


def test_conversation_activate_leaf_sets_id():
    conv = Conversation.create(user_id=uuid.uuid4())
    msg_id = uuid.uuid4()
    conv.active_leaf_id = msg_id
    assert conv.active_leaf_id == msg_id


def test_conversation_update_title():
    conv = Conversation.create(user_id=uuid.uuid4(), title="Old")
    conv.update_title("New Title")
    assert conv.title == "New Title"


def test_message_create_sets_role_and_content():
    conv_id = uuid.uuid4()
    msg = Message.create(conversation_id=conv_id, role="human", content="hello")
    assert msg.role == "human"
    assert msg.content == "hello"
    assert msg.conversation_id == conv_id
    assert msg.id is not None


def test_message_create_with_parent():
    conv_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    msg = Message.create(
        conversation_id=conv_id,
        role="ai",
        content="reply",
        parent_id=parent_id,
    )
    assert msg.parent_id == parent_id
