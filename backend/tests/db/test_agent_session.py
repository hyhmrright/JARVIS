from app.db.models import AgentSession, Conversation, Message, User


async def test_create_agent_session(db_session):
    user = User(email="sess@test.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()

    conv = Conversation(user_id=user.id, title="test")
    db_session.add(conv)
    await db_session.flush()

    session = AgentSession(
        conversation_id=conv.id, agent_type="main", status="active", depth=0
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    assert session.id is not None
    assert session.agent_type == "main"
    assert session.status == "active"
    assert session.depth == 0


async def test_parent_child_session(db_session):
    user = User(email="parent@test.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()

    conv = Conversation(user_id=user.id, title="test")
    db_session.add(conv)
    await db_session.flush()

    parent = AgentSession(conversation_id=conv.id, agent_type="main", depth=0)
    db_session.add(parent)
    await db_session.flush()

    child = AgentSession(
        conversation_id=conv.id,
        parent_session_id=parent.id,
        agent_type="subagent",
        depth=1,
    )
    db_session.add(child)
    await db_session.commit()
    await db_session.refresh(child)

    assert child.parent_session_id == parent.id
    assert child.depth == 1


async def test_message_agent_session_fk(db_session):
    user = User(email="msgfk@test.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()

    conv = Conversation(user_id=user.id, title="test")
    db_session.add(conv)
    await db_session.flush()

    session = AgentSession(conversation_id=conv.id, agent_type="main", depth=0)
    db_session.add(session)
    await db_session.flush()

    msg = Message(
        conversation_id=conv.id,
        agent_session_id=session.id,
        role="ai",
        content="hello",
    )
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)

    assert msg.agent_session_id == session.id


async def test_message_without_session(db_session):
    """Messages can still be created without an agent session (backward compat)."""
    user = User(email="nomsg@test.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()

    conv = Conversation(user_id=user.id, title="test")
    db_session.add(conv)
    await db_session.flush()

    msg = Message(conversation_id=conv.id, role="human", content="hi")
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)

    assert msg.agent_session_id is None
