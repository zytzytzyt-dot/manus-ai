from typing import List, Optional

from pydantic import Field

from app.agents.base import BaseAgent
from app.models.task import Task
from app.models.result import Result
from app.models.plan import Plan, PlanStep

class PlannerAgent(BaseAgent):
    """Agent responsible for creating execution plans.
    
    Analyzes tasks and creates structured plans with discrete steps
    for execution by other agents.
    """
    name: str = "PlannerAgent"
    description: str = "Creates execution plans for complex tasks"
    
    # Planner-specific fields
    planning_template: str = Field(
        default="""
        Task: {task}
        
        Create a step-by-step plan to accomplish this task.
        For each step, specify:
        1. The goal of the step
        2. The agent type best suited for this step (Executor, Validator)
        3. Required tools or resources
        4. Success criteria for the step
        
        Format the plan as a numbered list with these components clearly labeled.
        """
    )
    
    max_plan_steps: int = Field(default=10, description="Maximum steps in a plan")
    
    async def initialize(self):
        """初始化执行代理
        
        确保代理使用全局工具注册表
        """
        from app.tools import get_tool_registry
        
        self.tools = get_tool_registry()
        
        return True

    async def process(self, task: Task) -> Result:
        """Process a task by creating an execution plan.
        
        Args:
            task: The task to analyze and plan for
            
        Returns:
            Result containing the execution plan
        """
        self.context.add_message("system", "Creating execution plan for task")
        self.context.add_message("user", task.description)
        
        plan = await self._create_plan(task)
        
        return Result(
            task_id=task.id,
            content=f"Plan created with {len(plan.steps)} steps",
            metadata={"plan": plan.model_dump()},
            status="success"
        )
    
    async def step(self) -> bool:
        """Execute a planning step - not used in the standard process."""
        # Planner typically creates plans in a single operation
        return False
    
    async def _create_plan(self, task: Task) -> Plan:
        """Create an execution plan for the given task.
        
        Args:
            task: The task to plan for
            
        Returns:
            Structured execution plan
        """
        # Build planning prompt
        planning_prompt = self.planning_template.format(task=task.description)
        
        # Get planning response from LLM
        response = await self.tools.get_tool("llm").execute(
        prompt=planning_prompt,
        messages=[
                {"role": "system", "content": "You are a strategic planner for AI agents."},
                {"role": "user",   "content": planning_prompt}
            ]
        )
        
        # Parse response into structured plan
        plan_steps = self._parse_plan_steps(response.get("content", ""))
        
        return Plan(
            task_id=task.id,
            description=f"Plan for: {task.description}",
            steps=plan_steps
        )
    
    def _parse_plan_steps(self, plan_text: str) -> List[PlanStep]:
        """Parse plan text into structured plan steps.
        
        Args:
            plan_text: The raw plan text from LLM
            
        Returns:
            List of structured plan steps
        """
        steps = []
        
        # Simple parsing logic for demonstration
        # In a real implementation, use regex or more sophisticated parsing
        lines = plan_text.strip().split("\n")
        current_step = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for new step
            if line[0].isdigit() and "." in line[:5]:
                # Save previous step if exists
                if current_step and current_step.description:
                    steps.append(current_step)
                    
                # Start new step
                step_num = int(line[0])
                description = line[line.find(".")+1:].strip()
                current_step = PlanStep(
                    id=str(step_num),
                    description=description,
                    agent_type="Executor",  # Default
                    tools=[],
                    status="pending"
                )
                
            # Add details to current step
            elif current_step:
                if "agent" in line.lower() or "type" in line.lower():
                    for agent_type in ["Executor", "Validator"]:
                        if agent_type.lower() in line.lower():
                            current_step.agent_type = agent_type
                            
                elif "tool" in line.lower() or "resource" in line.lower():
                    tools = [t.strip() for t in line.split(":")[1].split(",") if t.strip()]
                    current_step.tools.extend(tools)
        
        # Add final step
        if current_step and current_step.description:
            steps.append(current_step)
            
        return steps[:self.max_plan_steps]  # Limit to max steps