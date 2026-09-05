"""JSON-based storage for conversations."""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from .config import DATA_DIR


def ensure_data_dir():
    """Ensure the data directory exists."""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def get_conversation_path(conversation_id: str) -> str:
    """Get the file path for a conversation."""
    return os.path.join(DATA_DIR, f"{conversation_id}.json")


def create_conversation(
    conversation_id: str,
    council_id: Optional[str] = None,
    council_name: Optional[str] = None,
    council_models: Optional[List[str]] = None,
    chairman_model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new conversation.

    Args:
        conversation_id: Unique identifier for the conversation
        council_id: Associated council profile ID
        council_name: Associated council display name
        council_models: Snapshot of models in the council
        chairman_model: Snapshot of chairman model

    Returns:
        New conversation dict
    """
    ensure_data_dir()

    conversation = {
        "id": conversation_id,
        "created_at": datetime.utcnow().isoformat(),
        "title": "New Conversation",
        "tags": [],
        "council_id": council_id,
        "council_name": council_name,
        "council_models": council_models,
        "chairman_model": chairman_model,
        "messages": []
    }

    # Save to file
    path = get_conversation_path(conversation_id)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(conversation, f, indent=2, ensure_ascii=False)

    return conversation


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        Conversation dict or None if not found
    """
    path = get_conversation_path(conversation_id)

    if not os.path.exists(path):
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def save_conversation(conversation: Dict[str, Any]):
    """
    Save a conversation to storage.

    Args:
        conversation: Conversation dict to save
    """
    ensure_data_dir()

    path = get_conversation_path(conversation['id'])
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(conversation, f, indent=2, ensure_ascii=False)


def list_conversations() -> List[Dict[str, Any]]:
    """
    List all conversations (metadata only).

    Returns:
        List of conversation metadata dicts
    """
    ensure_data_dir()

    conversations = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.json') and not filename.startswith('councils') and not filename.startswith('council_config'):
            path = os.path.join(DATA_DIR, filename)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if not isinstance(data, dict) or "id" not in data or "messages" not in data:
                        continue
                    # Return metadata only
                    conversations.append({
                        "id": data["id"],
                        "created_at": data["created_at"],
                        "title": data.get("title", "New Conversation"),
                        "tags": data.get("tags", []),
                        "council_id": data.get("council_id"),
                        "council_name": data.get("council_name"),
                        "message_count": len(data["messages"])
                    })
            except Exception:
                continue

    # Sort by creation time, newest first
    conversations.sort(key=lambda x: x["created_at"], reverse=True)

    return conversations


def add_user_message(conversation_id: str, content: str):
    """
    Add a user message to a conversation.

    Args:
        conversation_id: Conversation identifier
        content: User message content
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    # If last message is already an unanswered user message with the same content, don't duplicate
    if conversation.get("messages") and conversation["messages"][-1].get("role") == "user" and conversation["messages"][-1].get("content") == content:
        return

    conversation["messages"].append({
        "role": "user",
        "content": content
    })

    save_conversation(conversation)


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any]
):
    """
    Add an assistant message with all 3 stages to a conversation.

    Args:
        conversation_id: Conversation identifier
        stage1: List of individual model responses
        stage2: List of model rankings
        stage3: Final synthesized response
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "assistant",
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3
    })

    save_conversation(conversation)


def update_conversation_title(conversation_id: str, title: str):
    """
    Update the title of a conversation.

    Args:
        conversation_id: Conversation identifier
        title: New title for the conversation
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["title"] = title
    save_conversation(conversation)


def update_conversation_tags(conversation_id: str, tags: List[str]) -> Optional[Dict[str, Any]]:
    """
    Update tags for a conversation.

    Args:
        conversation_id: Conversation identifier
        tags: List of tag strings

    Returns:
        Updated conversation or None if not found
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        return None

    conversation["tags"] = tags
    save_conversation(conversation)
    return conversation


def get_all_tags() -> List[str]:
    """
    Get all unique tags across all conversations.

    Returns:
        Sorted list of unique tag strings
    """
    ensure_data_dir()

    tags = set()
    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.json'):
            path = os.path.join(DATA_DIR, filename)
            with open(path, 'r') as f:
                data = json.load(f)
                tags.update(data.get("tags", []))

    return sorted(list(tags))


def filter_conversations_by_tag(tag: str) -> List[Dict[str, Any]]:
    """
    Get conversations that have a specific tag.

    Args:
        tag: Tag to filter by

    Returns:
        List of conversation metadata dicts that have the tag
    """
    all_convs = list_conversations()
    return [conv for conv in all_convs if tag in conv.get("tags", [])]


def delete_conversation(conversation_id: str) -> bool:
    """
    Delete a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        True if deleted, False if not found
    """
    path = get_conversation_path(conversation_id)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False

