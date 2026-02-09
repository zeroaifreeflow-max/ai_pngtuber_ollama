import json
import os
from typing import Dict, Any, List
from src.config import Config

def load_memory() -> Dict[str, Any]:
    """Load memory from JSON file."""
    if not Config.MEMORY_PATH.exists():
        default_memory = {
            "user_profile": {},
            "facts": [],
            "last_conversation_topic": ""
        }
        save_memory(default_memory)
        return default_memory
    
    try:
        with open(Config.MEMORY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[Memory Error] Load failed: {e}")
        return {"user_profile": {}, "facts": [], "last_conversation_topic": ""}

def save_memory(memory_data: Dict[str, Any]) -> None:
    """Save memory to JSON file."""
    try:
        os.makedirs(os.path.dirname(Config.MEMORY_PATH), exist_ok=True)
        with open(Config.MEMORY_PATH, 'w', encoding='utf-8') as f:
            json.dump(memory_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[Memory Error] Save failed: {e}")

def update_memory(category: str, key: str, value: Any) -> None:
    """Update a specific piece of memory."""
    memory = load_memory()
    
    if category == "user_profile":
        memory["user_profile"][key] = value
    elif category == "facts":
        if value and value not in memory["facts"]:
            memory["facts"].append(value)
    elif category == "topic":
        memory["last_conversation_topic"] = value
        
    save_memory(memory)

def get_memory_context() -> str:
    """Convert memory into a formatted string for the System Prompt."""
    memory = load_memory()
    
    lines = ["--- [LONG TERM MEMORY] ---"]
    
    if memory.get("user_profile"):
        lines.append("User Profile:")
        for k, v in memory["user_profile"].items():
            lines.append(f"- {k}: {v}")
            
    if memory.get("facts"):
        lines.append("Key Facts to Remember:")
        for fact in memory["facts"]:
            lines.append(f"- {fact}")
            
    if memory.get("last_conversation_topic"):
        lines.append(f"Last Topic Discussed: {memory['last_conversation_topic']}")
        
    lines.append("--------------------------")
    return "\n".join(lines)
