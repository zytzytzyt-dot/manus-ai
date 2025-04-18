from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.models.task import Task
from app.memory.context import Context
from app.models.result import Result
from app.tools.tool_registry import ToolRegistry
from app.tools import get_tool_registry  # 添加这一行
import uuid

class BaseAgent(BaseModel, ABC):
    """Abstract base class for all agents in the system."""
    
    name: str = Field(..., description="Unique name identifying the agent")
    description: Optional[str] = Field(None, description="Agent description")
    
    # Core components
    context: Context = Field(default_factory=Context)
    tools: ToolRegistry = Field(default_factory=get_tool_registry) 
    
    # Execution state
    max_steps: int = Field(default=10, description="Maximum execution steps")
    current_step: int = Field(default=0, description="Current execution step")
    
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "extra": "allow"
    }
    
    @model_validator(mode="after")
    def initialize_agent(self) -> "BaseAgent":
        """Initialize agent components if not provided."""
        if not isinstance(self.context, Context):
            self.context = Context()
        return self
    
    @asynccontextmanager
    async def execution_context(self):
        """Context manager for handling agent execution lifecycle."""
        self.current_step = 0
        try:
            yield
        except Exception as e:
            self.context.add_error(f"Execution error: {str(e)}")
            raise
        finally:
            # Cleanup resources
            await self.cleanup()
    
    @abstractmethod
    async def process(self, task: Task) -> Result:
        """Process a task and return a result.
        
        Args:
            task: The task to process
            
        Returns:
            Result of task processing
        """
        pass
    
    @abstractmethod
    async def step(self) -> bool:
        """Execute a single step in the agent's workflow.
        
        Returns:
            True if processing should continue, False if completed
        """
        pass
    
    async def run(self, task: Task) -> Result:
        """Run the agent on a task.
        
        Args:
            task: The task to execute
            
        Returns:
            Result of the execution
        """
        async with self.execution_context():
            result = await self.process(task)
            return result
    
    async def cleanup(self):
        """Clean up resources used by the agent."""
        # Base implementation - override in subclasses
        pass

    async def process_task(self, task_description: str) -> str:
        # 创建任务对象
        task = Task(
            id=str(uuid.uuid4()),
            description=task_description
        )
        
        # 使用process方法处理任务
        result = await self.process(task)
        
        # 返回结果内容
        return result.content
