from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, ClassVar
from pydantic import BaseModel, Field

class BaseTool(BaseModel, ABC):
    """Base class for all tools in the system.
    
    Provides the foundation for tool definition and execution.
    """
    name: str = Field(..., description="Unique name of the tool")
    description: str = Field(..., description="Description of what the tool does")
    parameters: Dict = Field(default_factory=dict, description="JSON schema of parameters")
    
    class Config:
        arbitrary_types_allowed = True
        extra = "allow"
    
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool with provided parameters.
        
        Args:
            **kwargs: Parameters for tool execution
            
        Returns:
            Execution result
        """
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the tool's schema definition.
        
        Returns:
            Dictionary containing tool schema
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }
    
    async def cleanup(self):
        """Clean up any resources used by the tool."""
        # Base implementation - override in subclasses if needed
        pass


class ToolResult(BaseModel):
    """Standard result type for tool execution."""
    
    output: Optional[str] = Field(None, description="Text output of the tool")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional result data")
    base64_image: Optional[str] = Field(None, description="Base64-encoded image if applicable")
    
    def __str__(self) -> str:
        """String representation of the tool result."""
        if self.error:
            return f"Error: {self.error}"
        return self.output or ""
    
    @property
    def success(self) -> bool:
        """Check if the tool execution was successful."""
        return self.error is None