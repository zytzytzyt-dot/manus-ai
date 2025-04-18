import asyncio
import uuid
from typing import Dict, List, Optional, Any, Type

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.agents.planner import PlannerAgent
from app.agents.executor import ExecutorAgent
from app.agents.validator import ValidatorAgent
from app.models.task import Task
from app.models.result import Result
from app.models.plan import Plan, PlanStep
from app.memory.context import Context

class AgentRegistry(BaseModel):
    """Registry for managing agent instances."""
    
    agents: Dict[str, BaseAgent] = Field(default_factory=dict)
    
    def register(self, agent: BaseAgent) -> None:
        """Register an agent in the registry.
        
        Args:
            agent: The agent to register
        """
        self.agents[agent.name] = agent
    
    def get(self, agent_name: str) -> Optional[BaseAgent]:
        """Get an agent by name.
        
        Args:
            agent_name: Name of the agent to retrieve
            
        Returns:
            The agent instance or None if not found
        """
        return self.agents.get(agent_name)
    
    def get_by_type(self, agent_type: str) -> Optional[BaseAgent]:
        """Get an agent by type string.
        
        Args:
            agent_type: Type of agent to retrieve (e.g., "Executor")
            
        Returns:
            The agent instance or None if not found
        """
        for agent in self.agents.values():
            if agent.name == agent_type or agent.__class__.__name__ == agent_type:
                return agent
        return None
    
    def get_all(self) -> List[BaseAgent]:
        """Get all registered agents.
        
        Returns:
            List of all agent instances
        """
        return list(self.agents.values())

from typing import Dict, List, Optional, Any, ClassVar
from pydantic import BaseModel, Field

class OrchestratorAgent(BaseAgent):
    """Agent responsible for coordinating the multi-agent system."""
    
    name: ClassVar[str] = "OrchestratorAgent"
    description: ClassVar[str] = "Coordinates the multi-agent system workflow"
    
    # Orchestrator-specific attributes
    agent_registry: AgentRegistry = Field(default_factory=AgentRegistry)
    task_storage: Dict[str, Any] = Field(default_factory=dict)
    
    planner: Optional["PlannerAgent"] = Field(default=None)
    executor: Optional["ExecutorAgent"] = Field(default=None)
    validator: Optional["ValidatorAgent"] = Field(default=None)
    
    def __init__(self, **data):
        super().__init__(**data)
        # Register default agents
        self._register_default_agents()
    
    def _register_default_agents(self) -> None:
        """Register the default set of agents."""
        self.planner = PlannerAgent()
        self.executor = ExecutorAgent()
        self.validator = ValidatorAgent()
        
        self.agent_registry.register(self.planner)
        self.agent_registry.register(self.executor)
        self.agent_registry.register(self.validator)

    async def initialize(self):

        from app.memory.base import Memory
        
        self.memory = Memory()
        await self.memory.initialize()
        
        if hasattr(self.planner, 'initialize') and callable(self.planner.initialize):
            await self.planner.initialize()
        
        if hasattr(self.executor, 'initialize') and callable(self.executor.initialize):
            await self.executor.initialize()
        
        if hasattr(self.validator, 'initialize') and callable(self.validator.initialize):
            await self.validator.initialize()
        
        return True
    
    async def process(self, task: Task) -> Result:
        """Process a task using the multi-agent orchestration workflow.
        
        Args:
            task: The task to process
            
        Returns:
            Final result of the multi-agent processing
        """
        # Store task
        self.task_storage[task.id] = {
            "task": task,
            "results": [],
            "status": "in_progress"
        }
        
        try:
            # 1. Planning Phase
            self.context.add_message("system", "Starting planning phase")
            plan_result = await self._run_planning_phase(task)
            
            if plan_result.status != "success":
                return self._create_error_result(task, "Planning phase failed", plan_result.metadata)
            
            # 2. Execution Phase
            self.context.add_message("system", "Starting execution phase")
            execution_results = await self._run_execution_phase(task, plan_result)
            
            if not execution_results:
                return self._create_error_result(task, "Execution phase failed", {"steps_completed": 0})
            
            # 3. Validation Phase
            self.context.add_message("system", "Starting validation phase")
            validation_result = await self._run_validation_phase(task, execution_results)
            
            # 4. Summarize and return final result
            final_result = await self._create_final_result(task, plan_result, execution_results, validation_result)
            
            # Update task status
            self.task_storage[task.id]["status"] = "completed"
            
            return final_result
            
        except Exception as e:
            self.context.add_error(f"Orchestration error: {str(e)}")
            self.task_storage[task.id]["status"] = "failed"
            return self._create_error_result(task, f"Orchestration failed: {str(e)}")
    
    async def step(self) -> bool:
        """The orchestrator doesn't use step-by-step execution."""
        return False
    
    async def _run_planning_phase(self, task: Task) -> Result:
        """Run the planning phase to create an execution plan.
        
        Args:
            task: The task to create a plan for
            
        Returns:
            Planning result
        """
        planner = self.agent_registry.get("PlannerAgent")
        if not planner:
            return self._create_error_result(task, "Planner agent not found")
            
        return await planner.process(task)
    
    async def _run_execution_phase(self, task: Task, plan_result: Result) -> List[Result]:
        """Run the execution phase to implement the plan.
        
        Args:
            task: The original task
            plan_result: The planning result containing the plan
            
        Returns:
            List of execution results for each step
        """
        # Extract plan from planning result
        plan_data = plan_result.metadata.get("plan", {})
        if not plan_data:
            return []
            
        plan = Plan(**plan_data)
        
        # Execute each plan step
        results = []
        for step in plan.steps:
            # Create subtask for this step
            step_task = Task(
                id=f"{task.id}_step_{step.id}",
                description=step.description,
                metadata={
                    "parent_task_id": task.id,
                    "plan_step_id": step.id,
                    "tools": step.tools
                }
            )
            
            # Get appropriate agent for this step
            agent = self.agent_registry.get_by_type(step.agent_type)
            if not agent:
                self.context.add_error(f"Agent not found for type: {step.agent_type}")
                continue
                
            # Execute step
            step_result = await agent.process(step_task)
            results.append(step_result)
            
            # Update step status in plan
            step.status = step_result.status
        
        return results
    
    async def _run_validation_phase(self, task: Task, execution_results: List[Result]) -> Result:
        """Run the validation phase to evaluate execution results.
        
        Args:
            task: The original task
            execution_results: Results from the execution phase
            
        Returns:
            Validation result
        """
        # Create validation task
        validation_task = Task(
            id=f"{task.id}_validation",
            description=f"Validate results for task: {task.description}",
            metadata={
                "parent_task_id": task.id,
                "execution_result": "\n".join([r.content for r in execution_results]),
                "success_criteria": task.metadata.get("success_criteria", "Task completion")
            }
        )
        
        # Get validator agent
        validator = self.agent_registry.get("ValidatorAgent")
        if not validator:
            return self._create_error_result(task, "Validator agent not found")
            
        return await validator.process(validation_task)
    
    async def _create_final_result(
        self, 
        task: Task, 
        plan_result: Result, 
        execution_results: List[Result], 
        validation_result: Result
    ) -> Result:
        """Create the final comprehensive result.
        
        Args:
            task: The original task
            plan_result: Results from planning phase
            execution_results: Results from execution phase
            validation_result: Results from validation phase
            
        Returns:
            Final result combining all phases
        """
        # Combine results from all phases
        summary = f"Task Execution Summary\n=====================\n\n"
        summary += f"Task: {task.description}\n\n"
        
        # Add planning summary
        plan_data = plan_result.metadata.get("plan", {})
        if plan_data:
            plan = Plan(**plan_data)
            summary += f"Plan: {len(plan.steps)} steps\n\n"
        
        # Add execution summary
        summary += "Execution:\n"
        for i, result in enumerate(execution_results):
            summary += f"- Step {i+1}: {result.status.upper()}\n"
            # Add brief result excerpt (first 100 chars)
            result_excerpt = result.content[:100] + "..." if len(result.content) > 100 else result.content
            summary += f"  {result_excerpt}\n"
        
        # Add validation summary
        summary += "\nValidation:\n"
        summary += f"- Score: {validation_result.metadata.get('score', 0)}/100\n"
        summary += f"- Passed: {validation_result.metadata.get('passed', False)}\n"
        
        feedback = validation_result.metadata.get('feedback', [])
        if feedback:
            summary += "- Feedback:\n"
            for point in feedback:
                summary += f"  * {point}\n"
        
        # Final result
        return Result(
            task_id=task.id,
            content=summary,
            metadata={
                "plan": plan_result.metadata.get("plan", {}),
                "execution_results": [r.model_dump() for r in execution_results],
                "validation": validation_result.metadata
            },
            status="success" if validation_result.metadata.get('passed', False) else "partial"
        )
    def _create_error_result(self, task: Task, error_message: str, metadata: Dict = None) -> Result:
        """Create an error result.
        
        Args:
            task: The task that encountered an error
            error_message: Description of the error
            metadata: Optional additional metadata
            
        Returns:
            Error result
        """
        return Result(
            task_id=task.id,
            content=f"Error: {error_message}",
            metadata=metadata or {},
            status="error"
        )
    async def process_task(self, task_description: str) -> str:
        task = Task(
            id=str(uuid.uuid4()),
            description=task_description
        )
        
        result = await self.process(task)
        
        return result.content
