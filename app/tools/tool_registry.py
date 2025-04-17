from typing import Dict, List, Optional, Type, Union

from pydantic import BaseModel, Field

from app.tools.base import BaseTool
from app.utils.logger import get_logger

# Set up logger
logger = get_logger(__name__)

class ToolRegistry(BaseModel):
    """Registry for managing and accessing tools.
    
    Provides a central repository for tool registration, discovery,
    and access within the system.
    """
    tools: Dict[str, BaseTool] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True
    
    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool in the registry.
        
        Args:
            tool: The tool instance to register
            
        Raises:
            ValueError: If a tool with the same name already exists
        """
        if tool.name in self.tools:
            raise ValueError(f"Tool with name '{tool.name}' already registered")
            
        self.tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")
    
    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is registered.
        
        Args:
            tool_name: Name of the tool to check
            
        Returns:
            True if tool exists, False otherwise
        """
        return tool_name in self.tools
    
    def get_tool(self, tool_name: str) -> BaseTool:
        """Get a tool by name.
        
        Args:
            tool_name: Name of the tool to retrieve
            
        Returns:
            The tool instance
            
        Raises:
            ValueError: If tool not found
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found in registry")
            
        return self.tools[tool_name]
    
    def get_all_tools(self) -> List[BaseTool]:
        """Get all registered tools.
        
        Returns:
            List of all tool instances
        """
        return list(self.tools.values())
    
    def get_tool_schemas(self) -> List[Dict]:
        """Get the schemas for all registered tools.
        
        Returns:
            List of tool schema dictionaries
        """
        return [tool.get_schema() for tool in self.tools.values()]
    
    def get_tool_names(self) -> List[str]:
        """Get the names of all registered tools.
        
        Returns:
            List of tool names
        """
        return list(self.tools.keys())
    
    def unregister_tool(self, tool_name: str) -> None:
        """Unregister a tool from the registry.
        
        Args:
            tool_name: Name of the tool to unregister
            
        Raises:
            ValueError: If tool not found
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found in registry")
            
        del self.tools[tool_name]
        logger.debug(f"Unregistered tool: {tool_name}")
    
    async def cleanup(self) -> None:
        """Clean up all registered tools."""
        for tool_name, tool in self.tools.items():
            try:
                if hasattr(tool, "cleanup"):
                    await tool.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up tool '{tool_name}': {str(e)}")