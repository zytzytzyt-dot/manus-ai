import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


class Result(BaseModel):
    """Represents a result from task processing.
    
    Encapsulates the output of task execution with status and metadata.
    """
    task_id: str = Field(..., description="ID of the task that produced this result")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique result identifier")
    timestamp: datetime = Field(default_factory=datetime.now, description="Result creation time")
    status: str = Field(default="success", description="Result status")
    content: str = Field(..., description="Result content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    agent_id: Optional[str] = Field(None, description="ID of the agent that produced this result")
    
    @property
    def is_success(self) -> bool:
        """Check if result indicates success."""
        return self.status.lower() == "success"
    
    @property
    def is_error(self) -> bool:
        """Check if result indicates error."""
        return self.status.lower() == "error"
    
    @property
    def is_partial(self) -> bool:
        """Check if result is partial (incomplete)."""
        return self.status.lower() == "partial"
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to result.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value
    
    @classmethod
    def error_result(cls, task_id: str, error_message: str, metadata: Optional[Dict] = None) -> 'Result':
        """Create an error result.
        
        Args:
            task_id: Task ID
            error_message: Error message
            metadata: Optional metadata
            
        Returns:
            Error result
        """
        return cls(
            task_id=task_id,
            content=f"Error: {error_message}",
            status="error",
            metadata=metadata or {}
        )
    
    @classmethod
    def partial_result(cls, task_id: str, content: str, metadata: Optional[Dict] = None) -> 'Result':
        """Create a partial result.
        
        Args:
            task_id: Task ID
            content: Result content
            metadata: Optional metadata
            
        Returns:
            Partial result
        """
        return cls(
            task_id=task_id,
            content=content,
            status="partial",
            metadata=metadata or {}
        )
