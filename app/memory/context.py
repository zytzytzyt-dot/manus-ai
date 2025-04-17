import time
import uuid
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from app.memory.base import BaseMemory, MemoryItem

class Message(BaseModel):
    """Represents a message in a conversation context."""
    
    role: str = Field(..., description="Message role (user, system, assistant)")
    content: str = Field(..., description="Message content")
    timestamp: float = Field(default_factory=time.time, description="Message timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    

class Context(BaseModel):
    """Manages conversational context and memory for agents.
    
    Provides storage and retrieval of conversation messages and
    working memory for agent operations.
    """
    messages: List[Dict] = Field(default_factory=list, description="Conversation messages")
    memory: BaseMemory = Field(default_factory=BaseMemory, description="Working memory")
    max_messages: int = Field(default=100, description="Maximum messages to retain")
    
    class Config:
        arbitrary_types_allowed = True
    
    def add_message(self, role: str, content: str, **metadata) -> None:
        """Add a message to the conversation context.
        
        Args:
            role: Message role (user, system, assistant)
            content: Message content
            **metadata: Additional message metadata
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time()
        }
        
        if metadata:
            message["metadata"] = metadata
            
        self.messages.append(message)
        
        # Ensure we don't exceed max messages
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
    
    def add_user_message(self, content: str, **metadata) -> None:
        """Add a user message to the conversation.
        
        Args:
            content: Message content
            **metadata: Additional message metadata
        """
        self.add_message("user", content, **metadata)
    
    def add_system_message(self, content: str, **metadata) -> None:
        """Add a system message to the conversation.
        
        Args:
            content: Message content
            **metadata: Additional message metadata
        """
        self.add_message("system", content, **metadata)
    
    def add_assistant_message(self, content: str, **metadata) -> None:
        """Add an assistant message to the conversation.
        
        Args:
            content: Message content
            **metadata: Additional message metadata
        """
        self.add_message("assistant", content, **metadata)
    
    def add_error(self, error_message: str) -> None:
        """Add an error message to the conversation.
        
        Args:
            error_message: Error message content
        """
        self.add_system_message(f"Error: {error_message}", error=True)
    
    def get_recent_messages(self, n: int) -> List[Dict]:
        """Get the most recent messages.
        
        Args:
            n: Number of messages to retrieve
            
        Returns:
            List of recent messages
        """
        return self.messages[-n:] if self.messages else []
    
    def get_all_messages(self) -> List[Dict]:
        """Get all messages in the conversation.
        
        Returns:
            List of all messages
        """
        return self.messages.copy()
    
    def get_conversation_history(self, format_type: str = "simple") -> str:
        """Get formatted conversation history.
        
        Args:
            format_type: Format type (simple, detailed)
            
        Returns:
            Formatted conversation history
        """
        if format_type == "detailed":
            result = []
            for msg in self.messages:
                metadata = msg.get("metadata", {})
                metadata_str = ", ".join(f"{k}={v}" for k, v in metadata.items())
                result.append(f"[{msg['role']}] ({metadata_str}): {msg['content']}")
            return "\n".join(result)
        else:
            # Simple format
            result = []
            for msg in self.messages:
                prefix = {"user": "User", "system": "System", "assistant": "Assistant"}.get(
                    msg["role"], msg["role"].capitalize()
                )
                result.append(f"{prefix}: {msg['content']}")
            return "\n".join(result)
    
    def clear(self) -> None:
        """Clear all messages and memory."""
        self.messages = []
        self.memory.clear()
    
    def remember(self, content: Any, item_type: str = "note", **metadata) -> str:
        """Store an item in working memory.
        
        Args:
            content: Item content
            item_type: Type of memory item
            **metadata: Additional item metadata
            
        Returns:
            ID of stored item
        """
        memory_item = {
            "id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "type": item_type,
            "content": content,
            "metadata": metadata
        }
        
        return self.memory.add(memory_item)
    
    def recall(self, query: str, limit: int = 5) -> List[MemoryItem]:
        """Recall items from memory based on a query.
        
        Args:
            query: Search query
            limit: Maximum items to return
            
        Returns:
            List of relevant memory items
        """
        return self.memory.search(query, limit)
    
    def recall_by_type(self, item_type: str) -> List[MemoryItem]:
        """Recall all items of a specific type.
        
        Args:
            item_type: Type of items to retrieve
            
        Returns:
            List of matching items
        """
        return self.memory.get_by_type(item_type)
    
    def forget(self, item_id: str) -> bool:
        """Remove an item from memory.
        
        Args:
            item_id: ID of item to remove
            
        Returns:
            True if item removed, False if not found
        """
        return self.memory.remove(item_id)