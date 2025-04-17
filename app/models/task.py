import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


class Task(BaseModel):
    """Represents a task to be processed by the system.
    
    Encapsulates task details, metadata, and processing requirements.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique task identifier")
    description: str = Field(..., description="Task description")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation time")
    priority: int = Field(default=0, description="Task priority (higher = more important)")
    deadline: Optional[datetime] = Field(None, description="Task deadline")
    tags: List[str] = Field(default_factory=list, description="Task tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    parent_id: Optional[str] = Field(None, description="Parent task ID if this is a subtask")
    
    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if not self.deadline:
            return False
        return datetime.now() > self.deadline
    
    @property
    def time_until_deadline(self) -> Optional[float]:
        """Calculate time until deadline in seconds."""
        if not self.deadline:
            return None
        return (self.deadline - datetime.now()).total_seconds()
    
    @property
    def age(self) -> float:
        """Calculate task age in seconds."""
        return (datetime.now() - self.created_at).total_seconds()
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to task.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value
    
    def add_tag(self, tag: str) -> None:
        """Add a tag to task.
        
        Args:
            tag: Tag to add
        """
        if tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag: str) -> bool:
        """Remove a tag from task.
        
        Args:
            tag: Tag to remove
            
        Returns:
            True if tag was removed, False if not found
        """
        if tag in self.tags:
            self.tags.remove(tag)
            return True
        return False
    
    def has_tag(self, tag: str) -> bool:
        """Check if task has a tag.
        
        Args:
            tag: Tag to check
            
        Returns:
            True if task has tag
        """
        return tag in self.tags
    
    @classmethod
    def create_subtask(cls, parent: 'Task', description: str, **kwargs) -> 'Task':
        """Create a subtask of a parent task.
        
        Args:
            parent: Parent task
            description: Subtask description
            **kwargs: Additional task parameters
            
        Returns:
            Subtask
        """
        # Inherit parent tags if not specified
        if 'tags' not in kwargs:
            kwargs['tags'] = parent.tags.copy()
            
        # Create subtask
        subtask = cls(
            description=description,
            parent_id=parent.id,
            **kwargs
        )
        
        return subtask