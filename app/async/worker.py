import asyncio
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar
from datetime import datetime
import logging

from pydantic import BaseModel, Field

T = TypeVar('T')

class WorkerTask(BaseModel):
    """Represents a task for background processing."""
    
    id: str = Field(..., description="Unique task identifier")
    name: str = Field(..., description="Task name")
    status: str = Field(default="pending", description="Current status")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation time")
    priority: int = Field(default=0, description="Task priority (higher value = higher priority)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Task metadata")
    result: Optional[Any] = Field(None, description="Task result")
    error: Optional[str] = Field(None, description="Error message if failed")
    
    class Config:
        arbitrary_types_allowed = True


class Worker:
    """Background worker for processing tasks asynchronously.
    
    Provides a task queue with priority support for processing 
    asynchronous tasks in the background.
    """
    def __init__(self, num_workers: int = 2):
        """Initialize the worker.
        
        Args:
            num_workers: Number of worker tasks
        """
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.tasks: Dict[str, WorkerTask] = {}
        self.running = False
        self.workers: List[asyncio.Task] = []
        self.num_workers = num_workers
        self.logger = logging.getLogger("worker")
    
    async def start(self) -> None:
        """Start the worker."""
        if self.running:
            return
            
        self.running = True
        
        # Create worker tasks
        self.workers = [
            asyncio.create_task(self._worker_loop(i))
            for i in range(self.num_workers)
        ]
        
        self.logger.info(f"Started {self.num_workers} worker tasks")
    
    async def stop(self) -> None:
        """Stop the worker."""
        if not self.running:
            return
            
        self.running = False
        
        # Cancel all worker tasks
        for worker in self.workers:
            worker.cancel()
            
        # Wait for workers to finish
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)
            
        self.workers = []
        self.logger.info("Worker stopped")
    
    async def enqueue(
        self, 
        func: Callable[..., Awaitable[T]], 
        *args: Any, 
        name: str = None, 
        priority: int = 0, 
        **kwargs: Any
    ) -> str:
        """Enqueue a task for processing.
        
        Args:
            func: Coroutine function to execute
            *args: Positional arguments for function
            name: Task name
            priority: Task priority (higher value = higher priority)
            **kwargs: Keyword arguments for function
            
        Returns:
            Task ID
        """
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Create task
        task = WorkerTask(
            id=task_id,
            name=name or func.__name__,
            priority=priority
        )
        
        # Store task
        self.tasks[task_id] = task
        
        # Create queue item
        # Priority queue sorts by first element, so we negate priority
        # to get highest value first
        queue_item = (-priority, task_id, func, args, kwargs)
        
        # Add to queue
        await self.queue.put(queue_item)
        
        self.logger.debug(f"Enqueued task {task_id} ({task.name}) with priority {priority}")
        
        return task_id
    
    async def _worker_loop(self, worker_id: int) -> None:
        """Worker loop for processing tasks.
        
        Args:
            worker_id: Worker identifier
        """
        self.logger.debug(f"Worker {worker_id} started")
        
        while self.running:
            try:
                # Get task from queue
                priority, task_id, func, args, kwargs = await self.queue.get()
                
                # Update task status
                task = self.tasks.get(task_id)
                if not task:
                    self.queue.task_done()
                    continue
                    
                task.status = "running"
                
                # Execute task
                try:
                    result = await func(*args, **kwargs)
                    
                    # Update task status
                    task.status = "completed"
                    task.result = result
                    
                except Exception as e:
                    # Update task status on failure
                    task.status = "failed"
                    task.error = str(e)
                    
                    self.logger.error(f"Task {task_id} failed: {str(e)}", exc_info=True)
                    
                finally:
                    # Mark task as done
                    self.queue.task_done()
                
            except asyncio.CancelledError:
                # Worker cancelled
                break
                
            except Exception as e:
                self.logger.error(f"Worker {worker_id} error: {str(e)}", exc_info=True)
                
        self.logger.debug(f"Worker {worker_id} stopped")
    
    async def get_task(self, task_id: str) -> Optional[WorkerTask]:
        """Get a task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            WorkerTask or None if not found
        """
        return self.tasks.get(task_id)
    
    async def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> Optional[WorkerTask]:
        """Wait for a task to complete.
        
        Args:
            task_id: Task ID
            timeout: Optional timeout in seconds
            
        Returns:
            Completed task or None if timeout or not found
        """
        task = self.tasks.get(task_id)
        if not task:
            return None
            
        start_time = datetime.now()
        
        while task.status not in ["completed", "failed"]:
            # Check timeout
            if timeout is not None:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= timeout:
                    return None
                    
            # Wait a bit and check again
            await asyncio.sleep(0.1)
            
            # Refresh task data
            task = self.tasks.get(task_id)
            if not task:
                return None
                
        return task
    
    async def get_queue_info(self) -> Dict[str, Any]:
        """Get information about the task queue.
        
        Returns:
            Queue information
        """
        pending = await self.get_tasks_by_status("pending")
        running = await self.get_tasks_by_status("running")
        completed = await self.get_tasks_by_status("completed")
        failed = await self.get_tasks_by_status("failed")
        
        return {
            "queue_size": self.queue.qsize(),
            "pending_tasks": len(pending),
            "running_tasks": len(running),
            "completed_tasks": len(completed),
            "failed_tasks": len(failed),
            "worker_count": len(self.workers)
        }
    
    async def get_tasks_by_status(self, status: str) -> List[WorkerTask]:
        """Get tasks by status.
        
        Args:
            status: Task status
            
        Returns:
            List of matching tasks
        """
        return [task for task in self.tasks.values() if task.status == status]
    
    async def clean_completed_tasks(self, max_age_seconds: int = 3600) -> int:
        """Clean up old completed tasks.
        
        Args:
            max_age_seconds: Maximum age of tasks to keep
            
        Returns:
            Number of tasks removed
        """
        now = datetime.now()
        task_ids_to_remove = []
        
        # Find old completed/failed tasks
        for task_id, task in self.tasks.items():
            if task.status not in ["completed", "failed"]:
                continue
                
            age_seconds = (now - task.created_at).total_seconds()
            if age_seconds > max_age_seconds:
                task_ids_to_remove.append(task_id)
        
        # Remove tasks
        for task_id in task_ids_to_remove:
            del self.tasks[task_id]
                
        return len(task_ids_to_remove)