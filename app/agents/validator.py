from typing import Dict, List, Optional, Any

from pydantic import Field

from app.agents.base import BaseAgent
from app.models.task import Task
from app.models.result import Result

class ValidatorAgent(BaseAgent):
    """Agent responsible for validating the results of task execution.
    
    Evaluates execution results against success criteria and provides
    feedback on quality and completeness.
    """
    name: str = "ValidatorAgent"
    description: str = "Validates task execution results against criteria"
    
    # Validator-specific settings
    validation_template: str = Field(
        default="""
        Task: {task}
        
        Execution Result: {result}
        
        Success Criteria:
        {criteria}
        
        Please evaluate the execution result against the success criteria.
        For each criterion, provide:
        1. Pass/Fail status
        2. Justification for your assessment
        3. Suggestions for improvement if applicable
        
        Finally, provide an overall assessment and score (0-100).
        """
    )
    
    async def process(self, task: Task) -> Result:
        """Process a task by validating its results.
        
        Args:
            task: The task containing results to validate
            
        Returns:
            Validation result
        """
        # Get the execution result from task metadata
        execution_result = task.metadata.get("execution_result", "No execution result provided")
        success_criteria = task.metadata.get("success_criteria", "Task completion")
        
        self.context.add_message("system", "Validating task execution results")
        self.context.add_message("user", 
            f"Task: {task.description}\n\n"
            f"Result: {execution_result}\n\n"
            f"Validate against criteria: {success_criteria}"
        )
        
        validation_result = await self._validate(task.description, execution_result, success_criteria)
        
        return Result(
            task_id=task.id,
            content=validation_result.get("validation_text", "Validation completed"),
            metadata={
                "score": validation_result.get("score", 0),
                "passed": validation_result.get("passed", False),
                "feedback": validation_result.get("feedback", [])
            },
            status="success"
        )
    
    async def step(self) -> bool:
        """Execute a validation step - not used in the standard process."""
        # Validator typically validates in a single operation
        return False
    
    async def _validate(self, task: str, result: str, criteria: str) -> Dict[str, Any]:
        """Validate execution results against success criteria.
        
        Args:
            task: The original task description
            result: The execution result
            criteria: The success criteria
            
        Returns:
            Validation results dictionary
        """
        # Prepare validation prompt
        validation_prompt = self.validation_template.format(
            task=task,
            result=result,
            criteria=criteria
        )
        
        # Get validation response from LLM
        response = await self.tools.get_tool("llm").execute({
            "messages": [
                {"role": "system", "content": "You are a critical validator that evaluates task execution quality."},
                {"role": "user", "content": validation_prompt}
            ]
        })
        
        # Parse validation results
        validation_text = response.get("content", "")
        
        # Extract score (simple parsing for demonstration)
        score = 0
        for line in validation_text.split("\n"):
            if "score" in line.lower() and ":" in line:
                try:
                    score_text = line.split(":")[1].strip()
                    if "/" in score_text:
                        num, denom = score_text.split("/")
                        score = int(float(num.strip()) / float(denom.strip()) * 100)
                    else:
                        score = int(float(score_text.replace("%", "")))
                except (ValueError, IndexError):
                    score = 0
        
        # Determine pass/fail status
        passed = score >= 70  # 70% threshold for passing
        
        # Extract feedback points
        feedback = []
        collecting_feedback = False
        for line in validation_text.split("\n"):
            line = line.strip()
            if not line:
                continue
                
            if "improvement" in line.lower() or "suggestion" in line.lower():
                collecting_feedback = True
                continue
                
            if collecting_feedback and line.startswith("-"):
                feedback.append(line[1:].strip())
        
        return {
            "validation_text": validation_text,
            "score": score,
            "passed": passed,
            "feedback": feedback
        }