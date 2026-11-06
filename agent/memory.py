"""
Memory Module
Manages broker profiles and conversation history.
In production, this would use AgentCore Memory. Here we use local JSON storage.
"""

import json
import os
from datetime import datetime
from typing import Optional

# Local storage path
MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".memory")
PROFILES_FILE = os.path.join(MEMORY_DIR, "broker_profiles.json")
HISTORY_FILE = os.path.join(MEMORY_DIR, "conversation_history.json")


def _ensure_memory_dir():
    """Create memory directory if it doesn't exist."""
    os.makedirs(MEMORY_DIR, exist_ok=True)


def save_broker_profile(profile: dict) -> dict:
    """
    Save or update a broker profile.
    
    Args:
        profile: Dictionary with broker information:
            - name: Broker name
            - company: Company/firm
            - role: Job title
            - risk_tolerance: low/moderate/high/aggressive
            - investment_style: value/growth/dividend/momentum/balanced
            - sector_interests: Comma-separated sectors
            - client_demographics: Who their clients are
            - geographic_focus: Markets they focus on
            - news_sources: Preferred news feeds
    
    Returns:
        Saved profile with metadata
    """
    _ensure_memory_dir()
    
    # Load existing profiles
    profiles = _load_profiles()
    
    # Add metadata
    profile["updated_at"] = datetime.now().isoformat()
    if "created_at" not in profile:
        profile["created_at"] = datetime.now().isoformat()
    
    # Use name as key
    profile_key = profile.get("name", "default").lower().replace(" ", "_")
    profiles[profile_key] = profile
    
    # Save
    with open(PROFILES_FILE, "w") as f:
        json.dump(profiles, f, indent=2)
    
    return {"status": "saved", "profile_key": profile_key, "profile": profile}


def get_broker_profile(name: Optional[str] = None) -> Optional[dict]:
    """
    Retrieve a broker profile by name, or the most recently updated one.
    
    Args:
        name: Broker name (optional, returns latest if not specified)
    
    Returns:
        Broker profile dictionary or None
    """
    profiles = _load_profiles()
    
    if not profiles:
        return None
    
    if name:
        profile_key = name.lower().replace(" ", "_")
        return profiles.get(profile_key)
    
    # Return most recently updated
    latest = max(profiles.values(), key=lambda p: p.get("updated_at", ""))
    return latest


def list_broker_profiles() -> list:
    """List all saved broker profiles."""
    profiles = _load_profiles()
    return [
        {
            "name": p.get("name", "Unknown"),
            "company": p.get("company", "N/A"),
            "risk_tolerance": p.get("risk_tolerance", "N/A"),
            "updated_at": p.get("updated_at", "N/A"),
        }
        for p in profiles.values()
    ]


def save_conversation(role: str, content: str, metadata: Optional[dict] = None):
    """
    Save a conversation turn to history.
    
    Args:
        role: 'user' or 'assistant'
        content: Message content
        metadata: Optional metadata (tools used, stocks queried, etc.)
    """
    _ensure_memory_dir()
    
    history = _load_history()
    
    entry = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }
    if metadata:
        entry["metadata"] = metadata
    
    history.append(entry)
    
    # Keep last 100 messages
    history = history[-100:]
    
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def get_conversation_history(last_n: int = 20) -> list:
    """Get recent conversation history."""
    history = _load_history()
    return history[-last_n:]


def clear_conversation_history():
    """Clear all conversation history."""
    _ensure_memory_dir()
    with open(HISTORY_FILE, "w") as f:
        json.dump([], f)


def delete_broker_profile(name: str) -> bool:
    """Delete a broker profile by name."""
    profiles = _load_profiles()
    profile_key = name.lower().replace(" ", "_")
    if profile_key in profiles:
        del profiles[profile_key]
        with open(PROFILES_FILE, "w") as f:
            json.dump(profiles, f, indent=2)
        return True
    return False


# --- Internal Helpers ---

def _load_profiles() -> dict:
    """Load broker profiles from disk."""
    _ensure_memory_dir()
    if os.path.exists(PROFILES_FILE):
        try:
            with open(PROFILES_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _load_history() -> list:
    """Load conversation history from disk."""
    _ensure_memory_dir()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []
