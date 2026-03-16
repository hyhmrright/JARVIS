from app.db.models import Message, User, UserSettings


async def test_create_user(db_session):
    user = User(email="test@example.com", password_hash="hashed")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None
    assert user.is_active is True


async def test_user_has_settings_cascade(db_session):
    # NOTE: db_session wraps the test in a rolled-back transaction, so
    # commit() here flushes within that transaction rather than issuing a
    # real COMMIT. The cascade assertion below verifies ORM identity-map
    # eviction (cascade="all, delete-orphan"), not the database-level
    # ON DELETE CASCADE FK constraint.
    user = User(email="a@b.com", password_hash="x")
    settings = UserSettings(user=user)
    db_session.add(user)
    await db_session.commit()

    assert settings.model_provider == "deepseek"

    await db_session.refresh(settings)
    assert settings.id is not None

    await db_session.delete(user)
    await db_session.commit()
    result = await db_session.get(UserSettings, settings.id)
    assert result is None


async def test_message_parent_id_relationship(db_session):
    from app.db.models import Conversation, User

    user = User(email="test_msg@example.com", password_hash="x")
    db_session.add(user)
    await db_session.commit()

    conv = Conversation(user_id=user.id, title="Test")
    db_session.add(conv)
    await db_session.commit()

    parent_msg = Message(conversation_id=conv.id, role="human", content="Hello")
    db_session.add(parent_msg)
    await db_session.commit()

    child_msg = Message(
        conversation_id=conv.id, role="ai", content="Hi", parent_id=parent_msg.id
    )  # noqa: E501
    db_session.add(child_msg)
    await db_session.commit()

    assert child_msg.parent_id == parent_msg.id
