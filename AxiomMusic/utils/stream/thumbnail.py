# Thumbnail Toggle Management Module
# This file handles the thumbnail on/off toggle functionality for streams

# Dictionary to store thumbnail toggle status per chat
chat_thumbnail_status = {}


def get_thumbnail_status(chat_id):
    """
    Get thumbnail status for a specific chat.
    
    Args:
        chat_id: The ID of the chat/group
        
    Returns:
        str: "on" or "off" (default is "on")
    """
    return chat_thumbnail_status.get(chat_id, "on")


def toggle_thumbnail_status(chat_id):
    """
    Toggle the thumbnail status for a specific chat.
    Changes "on" to "off" and vice versa.
    
    Args:
        chat_id: The ID of the chat/group
        
    Returns:
        str: The new thumbnail status ("on" or "off")
    """
    current = get_thumbnail_status(chat_id)
    new_status = "off" if current == "on" else "on"
    chat_thumbnail_status[chat_id] = new_status
    return new_status


def set_thumbnail_status(chat_id, status):
    """
    Set the thumbnail status for a specific chat.
    
    Args:
        chat_id: The ID of the chat/group
        status: "on" or "off"
    """
    if status in ["on", "off"]:
        chat_thumbnail_status[chat_id] = status
    else:
        raise ValueError("Status must be 'on' or 'off'")


def reset_thumbnail_status(chat_id):
    """
    Reset thumbnail status for a chat to default (on).
    
    Args:
        chat_id: The ID of the chat/group
    """
    if chat_id in chat_thumbnail_status:
        del chat_thumbnail_status[chat_id]


def get_all_thumbnail_statuses():
    """
    Get all thumbnail statuses across all chats.
    
    Returns:
        dict: Dictionary mapping chat_id to status
    """
    return chat_thumbnail_status.copy()


def clear_all_statuses():
    """Clear all thumbnail statuses from memory."""
    global chat_thumbnail_status
    chat_thumbnail_status.clear()
