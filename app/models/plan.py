import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    """Represents a step in an execution plan."""
    
    id: str = Field(..., description="Step identifier")
    description: str = Field(..., description="Step description")
    agent_type: str = Field(..., description="Type of agent to execute this step")
    tools: List[str] = Field(default_factory=list, description="Tools required for this step")
    status: str = Field(default="pending", description="Step status")
    result_id: Optional[str] = Field(None, description="ID of the result for this step")
    dependencies: List[str] = Field(default_factory=list, description="IDs of steps this step depends on")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class Plan(BaseModel):
    """Represents an execution plan for a task.
    
    Encapsulates a structured plan with steps for task execution.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique plan identifier")
    task_id: str = Field(..., description="ID of the task this plan is for")
    created_at: datetime = Field(default_factory=datetime.now, description="Plan creation time")
    description: str = Field(..., description="Plan description")
    steps: List[PlanStep] = Field(..., description="Plan steps")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @property
    def is_complete(self) -> bool:
        """Check if plan is complete."""
        return all(step.status in ["completed", "skipped"] for step in self.steps)
    
    @property
    def progress(self) -> float:
        """Calculate plan progress (0.0 to 1.0)."""
        if not self.steps:
            return 1.0
            
        completed = sum(1 for step in self.steps if step.status in ["completed", "skipped"])
        return completed / len(self.steps)
    
    def get_step(self, step_id: str) -> Optional[PlanStep]:
        """Get a step by ID.
        
        Args:
            step_id: Step ID
            
        Returns:
            PlanStep or None if not found
        """
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    def get_next_steps(self) -> List[PlanStep]:
        """Get next executable steps.
        
        Returns steps that are pending and have all dependencies satisfied.
        
        Returns:
            List of executable steps
        """
        # Track completed step IDs
        completed_steps = {
            step.id for step in self.steps
            if step.status in ["completed", "skipped"]
        }
        
        # Find pending steps with satisfied dependencies
        next_steps = []
        for step in self.steps:
            if step.status != "pending":
                continue
                
            # Check if all dependencies are satisfied
            dependencies_satisfied = all(
                dep in completed_steps for dep in step.dependencies
            )
            
            if dependencies_satisfied:
                next_steps.append(step)
                
        return next_steps
    
    def update_step_status(self, step_id: str, status: str, result_id: Optional[str] = None) -> bool:
        """Update step status.
        
        Args:
            step_id: Step ID
            status: New status
            result_id: Optional result ID
            
        Returns:
            True if step was updated, False if not found
        """
        step = self.get_step(step_id)
        if not step:
            return False
            
        step.status = status
        if result_id:
            step.result_id = result_id
            
        return True
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to plan.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value