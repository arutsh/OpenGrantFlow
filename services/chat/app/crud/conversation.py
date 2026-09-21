"""CRUD for Conversation and Message — provider-neutral, per specs/chat-conversations.

Unlike ai's old chat_session store, message content here is plain text, not
a serialized LLM-provider wire format — no (de)serialization step is needed
to replay history back to ai, just a role/content projection.
"""

import uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message
from app.services.orchestrator import TurnResult
from shared.ai_client import ChatTurn

_MAX_HISTORY_MESSAGES = 50
_DEFAULT_CONVERSATIONS_LIMIT = 50
_DEFAULT_MESSAGES_LIMIT = 200


def _is_valid_uuid(value: str) -> bool:
    """conversation_id is client-supplied and reaches these lookups unvalidated —
    a malformed value would otherwise raise deep inside the GUID column's bind-param
    conversion (uuid.UUID(value)) as an uncaught ValueError. Treated the same as
    "not found" so it degrades gracefully instead of a bare 500.
    """
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


async def get_or_create_conversation(
    conversation_id: str | None,
    customer_id: str,
    user_id: str,
    db: AsyncSession,
) -> Conversation:
    """Return the existing conversation or create a new one.

    An unknown, malformed, or foreign id silently starts a fresh conversation
    rather than erroring — see specs/chat-conversations.md's "Stale id
    degrades gracefully" scenario.
    """
    now = datetime.now(timezone.utc)

    if conversation_id and _is_valid_uuid(conversation_id):
        result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        conversation = result.scalar_one_or_none()
        if conversation and str(conversation.customer_id) == customer_id:
            return conversation

    conversation = Conversation(
        id=str(uuid.uuid4()),
        customer_id=customer_id,
        user_id=user_id,
        message_count=0,
        last_activity_at=now,
        created_at=now,
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def load_history(conversation_id: str, db: AsyncSession) -> list[Message]:
    """Load the most recent messages for a conversation, oldest first, capped at 50."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(_MAX_HISTORY_MESSAGES)
    )
    rows = result.scalars().all()
    return list(reversed(rows))


def to_chat_turns(rows: Sequence[Message]) -> list[ChatTurn]:
    """Project stored rows to the role/content shape ai/decide expects.

    Tool rows (role != user/assistant) are skipped — ai only ever sees the
    conversational turns, never raw tool metadata.
    """
    turns = []
    for row in rows:
        if row.role in ("user", "assistant"):
            turns.append(ChatTurn(role=row.role, content=row.content))
    return turns


async def save_turn(
    conversation: Conversation,
    user_text: str,
    turn_result: TurnResult,
    db: AsyncSession,
) -> None:
    """Persist the user message and the assistant's reply for one completed turn."""
    now = datetime.now(timezone.utc)

    user_row = Message(
        id=str(uuid.uuid4()),
        conversation_id=str(conversation.id),
        role="user",
        content=user_text,
        created_at=now,
    )
    db.add(user_row)

    tool_result_json = None
    if turn_result.tool_name:
        tool_result_json = {"message": turn_result.tool_result}
        if turn_result.created_resource_id:
            tool_result_json["budget_id"] = turn_result.created_resource_id

    assistant_row = Message(
        id=str(uuid.uuid4()),
        conversation_id=str(conversation.id),
        role="assistant",
        content=turn_result.reply,
        tool_name=turn_result.tool_name,
        tool_params=turn_result.tool_params,
        tool_result=tool_result_json,
        created_at=now,
    )
    db.add(assistant_row)

    conversation.message_count = (conversation.message_count or 0) + 2
    conversation.last_activity_at = now
    await db.commit()


async def list_conversations(
    customer_id: str, db: AsyncSession, *, limit: int = _DEFAULT_CONVERSATIONS_LIMIT
) -> list[Conversation]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.customer_id == customer_id)
        .order_by(Conversation.last_activity_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_conversation_messages(
    conversation_id: str,
    customer_id: str,
    db: AsyncSession,
    *,
    limit: int = _DEFAULT_MESSAGES_LIMIT,
) -> list[Message] | None:
    """Return the conversation's most recent messages in chronological order, or
    None if the conversation doesn't exist, is malformed, or belongs to another
    customer."""
    if not _is_valid_uuid(conversation_id):
        return None

    owner_check = await db.execute(
        select(Conversation.id).where(
            Conversation.id == conversation_id, Conversation.customer_id == customer_id
        )
    )
    if owner_check.scalar_one_or_none() is None:
        return None

    messages_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    return list(reversed(messages_result.scalars().all()))
