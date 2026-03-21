import asyncio
import json
import uuid

from httpx import AsyncClient

from app.main import app
from app.db.models import Message
from app.db.session import AsyncSessionLocal
from sqlalchemy import select


async def reproduce():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 1. Create a user
        unique_email = f"test_{uuid.uuid4().hex[:8]}@test.com"
        await client.post(
            "/api/auth/register",
            json={"email": unique_email, "password": "password123"},
        )

        # 2. Login to get token
        resp = await client.post(
            "/api/auth/login",
            data={"username": unique_email, "password": "password123"},
        )
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Create a conversation
        resp = await client.post(
            "/api/conversations", json={"title": "Context Test"}, headers=headers
        )
        conv_id = resp.json()["id"]

        # 4. Send first message: "My name is Alice."
        print("\nSending first message: 'My name is Alice.'")
        resp = await client.post(
            "/api/chat/stream",
            json={"conversation_id": conv_id, "content": "My name is Alice."},
            headers=headers,
        )

        # Parse SSE to get AI message ID and Human message ID
        first_ai_msg_id = None
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if data.get("type") == "done":
                    first_ai_msg_id = data.get("ai_msg_id")
                if data.get("delta"):
                    print(data["delta"], end="", flush=True)
        print("\nFirst exchange done.")

        # 5. Send second message: "What is my name?"
        print("\nSending second message: 'What is my name?'")
        resp = await client.post(
            "/api/chat/stream",
            json={
                "conversation_id": conv_id,
                "content": "What is my name?",
                "parent_message_id": first_ai_msg_id,
            },
            headers=headers,
        )

        second_ai_content = ""
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if data.get("delta"):
                    second_ai_content += data["delta"]
                    print(data["delta"], end="", flush=True)
        print("\nSecond exchange done.")

        if "Alice" in second_ai_content:
            print("\nSUCCESS: Context maintained!")
        else:
            print("\nFAILURE: Context lost! AI replied:", second_ai_content)

        # 6. Verify database links
        async with AsyncSessionLocal() as db:
            messages = await db.scalars(
                select(Message)
                .where(Message.conversation_id == uuid.UUID(conv_id))
                .order_by(Message.created_at)
            )
            all_msgs = messages.all()
            print(f"\nTotal messages in DB: {len(all_msgs)}")
            for m in all_msgs:
                print(
                    f"ID: {m.id}, Role: {m.role}, Parent: {m.parent_id}, "
                    f"Content: {m.content[:20]}"
                )


if __name__ == "__main__":
    asyncio.run(reproduce())
