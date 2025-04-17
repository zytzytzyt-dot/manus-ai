from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

class MemoryItem(BaseModel):
    """Base class for items stored in memory."""
    
    id: str = Field(..., description="Unique identifier for the memory item")
    timestamp: float = Field(..., description="Creation timestamp")
    type: str = Field(..., description="Type of memory item")
    content: Any = Field(..., description="Item content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @property
    def age(self) -> float:
        """Calculate age of memory item in seconds."""
        import time
        return time.time() - self.timestamp
    
    def relevance_score(self, query: str) -> float:
        """Calculate relevance score for query.
        
        Args:
            query: Query to calculate relevance for
            
        Returns:
            Relevance score (0.0 to 1.0)
        """
        # Basic implementation - override in subclasses
        if not query:
            return 0.0
            
        # Simple keyword matching
        query_terms = set(query.lower().split())
        content_str = str(self.content).lower()
        
        matches = sum(1 for term in query_terms if term in content_str)
        return min(1.0, matches / max(1, len(query_terms)))


class BaseMemory(BaseModel):
    """Base class for memory implementations.
    
    Provides foundation for storing, retrieving, and managing memory items.
    """
    items: List[MemoryItem] = Field(default_factory=list, description="List of memory items")
    max_items: int = Field(default=1000, description="Maximum items to store")
    
    class Config:
        arbitrary_types_allowed = True
    
    def add(self, item: Union[MemoryItem, Dict]) -> str:
        """Add an item to memory.
        
        Args:
            item: Item to add (MemoryItem or dict)
            
        Returns:
            ID of added item
            
        Raises:
            ValueError: If item is invalid
        """
        # Convert dict to MemoryItem if needed
        if isinstance(item, dict):
            if "id" not in item:
                import uuid
                item["id"] = str(uuid.uuid4())
            if "timestamp" not in item:
                import time
                item["timestamp"] = time.time()
            if "type" not in item:
                item["type"] = "generic"
                
            item = MemoryItem(**item)
            
        # Add item to memory
        self.items.append(item)
        
        # Ensure we don't exceed max items
        if len(self.items) > self.max_items:
            self.items = self.items[-self.max_items:]
            
        return item.id
    
    def get(self, item_id: str) -> Optional[MemoryItem]:
        """Get an item by ID.
        
        Args:
            item_id: ID of item to retrieve
            
        Returns:
            Memory item or None if not found
        """
        for item in self.items:
            if item.id == item_id:
                return item
        return None
    
    def get_by_type(self, item_type: str) -> List[MemoryItem]:
        """Get all items of a specific type.
        
        Args:
            item_type: Type of items to retrieve
            
        Returns:
            List of matching items
        """
        return [item for item in self.items if item.type == item_type]
    
    def search(self, query: str, limit: int = 5) -> List[MemoryItem]:
        """Search memory for relevant items.
        
        Args:
            query: Search query
            limit: Maximum items to return
            
        Returns:
            List of most relevant items
        """
        # Calculate relevance scores
        scored_items = [
            (item, item.relevance_score(query))
            for item in self.items
        ]
        
        # Sort by relevance and limit results
        scored_items.sort(key=lambda x: x[1], reverse=True)
        return [item for item, score in scored_items[:limit] if score > 0]
    
    def remove(self, item_id: str) -> bool:
        """Remove an item from memory.
        
        Args:
            item_id: ID of item to remove
            
        Returns:
            True if item removed, False if not found
        """
        for i, item in enumerate(self.items):
            if item.id == item_id:
                self.items.pop(i)
                return True
        return False
    
    def clear(self) -> None:
        """Clear all items from memory."""
        self.items = []
    
    def size(self) -> int:
        """Get number of items in memory.
        
        Returns:
            Item count
        """
        return len(self.items)