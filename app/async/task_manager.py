import asyncio
import uuid
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field

class TaskStatus:
    """Task status constants."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AsyncTask(BaseModel):
    """Represents an asynchronous task."""
    
    id: str = Field(..., description="Unique task identifier")
    name: str = Field(..., description="Task name")
    status: str = Field(default=TaskStatus.PENDING, description="Current status")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation time")
    started_at: Optional[datetime] = Field(None, description="Start time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")
    result: Any = Field(None, description="Task result")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Task metadata")
    
    @property
    def duration(self) -> Optional[float]:
        """Calculate task duration in seconds."""
        if not self.started_at:
            return None
            
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds()
    
    @property
    def is_finished(self) -> bool:
        """Check if task is finished."""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]


class TaskManager:
    """Manages asynchronous task execution and tracking.
    
    Provides capabilities for scheduling, tracking, and managing
    asynchronous tasks.
    """
    def __init__(self):
        """Initialize the task manager."""
        self.tasks: Dict[str, AsyncTask] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        
    async def create_task(
        self, 
        coro: Callable, 
        name: str = None, 
        metadata: Dict[str, Any] = None
    ) -> AsyncTask:
        """Create and schedule a new task.
        
        Args:
            coro: Coroutine function to execute
            name: Task name
            metadata: Additional task metadata
            
        Returns:
            AsyncTask object
        """
        # Generate task ID and create task object
        task_id = str(uuid.uuid4())
        task_name = name or f"Task_{task_id[:8]}"
        
        task = AsyncTask(
            id=task_id,
            name=task_name,
            metadata=metadata or {}
        )
        
        # Store task
        async with self._lock:
            self.tasks[task_id] = task
        
        # Schedule task for execution
        asyncio_task = asyncio.create_task(
            self._execute_task(task_id, coro)
        )
        
        # Store running task
        self.running_tasks[task_id] = asyncio_task
        
        return task
    
    async def _execute_task(self, task_id: str, coro: Callable) -> None:
        """Execute a task and update its status.
        
        Args:
            task_id: Task ID
            coro: Coroutine function to execute
        """
        # Get task
        task = self.tasks.get(task_id)
        if not task:
            return
            
        # Update task status
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        try:
            # Execute coroutine
            result = await coro()
            
            # Update task status on success
            task.status = TaskStatus.COMPLETED
            task.result = result
            
        except asyncio.CancelledError:
            # Update task status on cancellation
            task.status = TaskStatus.CANCELLED
            task.error = "Task cancelled"
            
        except Exception as e:
            # Update task status on failure
            task.status = TaskStatus.FAILED
            task.error = str(e)
            
            # Log error
            import traceback
            print(f"Task {task_id} failed: {str(e)}")
            print(traceback.format_exc())
            
        finally:
            # Update completion time
            task.completed_at = datetime.now()
            
            # Remove from running tasks
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
    
    async def get_task(self, task_id: str) -> Optional[AsyncTask]:
        """Get a task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            AsyncTask or None if not found
        """
        return self.tasks.get(task_id)
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task.
        
        Args:
            task_id: Task ID
            
        Returns:
            True if task cancelled, False if not found or already finished
        """
        # Check if task exists and is running
        asyncio_task = self.running_tasks.get(task_id)
        if not asyncio_task:
            return False
            
        # Cancel task
        asyncio_task.cancel()
        
        # Wait for task to be cancelled
        try:
            await asyncio_task
        except asyncio.CancelledError:
            pass
            
        return True
    
    async def get_all_tasks(self) -> List[AsyncTask]:
        """Get all tasks.
        
        Returns:
            List of all tasks
        """
        return list(self.tasks.values())
    
    async def get_tasks_by_status(self, status: str) -> List[AsyncTask]:
        """Get tasks by status.
        
        Args:
            status: Task status
            
        Returns:
            List of matching tasks
        """
        return [task for task in self.tasks.values() if task.status == status]
    
    async def clean_up(self, max_age_seconds: int = 3600) -> int:
        """Clean up old completed tasks.
        
        Args:
            max_age_seconds: Maximum age of tasks to keep
            
        Returns:
            Number of tasks removed
        """
        now = datetime.now()
        task_ids_to_remove = []
        
        # Find old completed tasks
        for task_id, task in self.tasks.items():
            if not task.is_finished:
                continue
                
            if not task.completed_at:
                continue
                
            age_seconds = (now - task.completed_at).total_seconds()
            if age_seconds > max_age_seconds:
                task_ids_to_remove.append(task_id)
        
        # Remove tasks
        async with self._lock:
            for task_id in task_ids_to_remove:
                del self.tasks[task_id]
                
        return len(task_ids_to_remove)
    
    async def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> Optional[AsyncTask]:
        """Wait for a task to complete.
        
        Args:
            task_id: Task ID
            timeout: Optional timeout in seconds
            
        Returns:
            Completed task or None if timeout or not found
        """
        asyncio_task = self.running_tasks.get(task_id)
        if not asyncio_task:
            # Task not running, return current state
            return self.tasks.get(task_id)
        
        try:
            # Wait for task to complete
            await asyncio.wait_for(asyncio_task, timeout=timeout)
            return self.tasks.get(task_id)
        except asyncio.TimeoutError:
            # Timeout waiting for task
            return None
