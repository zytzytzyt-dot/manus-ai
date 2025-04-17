import asyncio
from typing import Dict, List, Optional, Any

from pydantic import Field

from app.agents.base import BaseAgent
from app.models.task import Task
from app.models.result import Result
from app.models.plan import PlanStep

class ExecutorAgent(BaseAgent):
    """Agent responsible for executing individual tasks or plan steps.
    
    Handles the actual work of interacting with tools and external systems 
    to accomplish specific goals.
    """
    name: str = "ExecutorAgent"
    description: str = "Executes tasks using available tools"
    
    # Executor-specific settings
    execution_template: str = Field(
        default="""
        Task: {task}
        
        You have access to the following tools:
        {tool_descriptions}
        
        Think step by step about how to solve this task using the available tools.
        For each step:
        1. Decide which tool to use
        2. Determine the parameters for the tool
        3. Execute the tool and analyze the results
        
        When you've completed the task or reached a blocking point, summarize your findings.
        """
    )
    
    max_tool_calls: int = Field(default=20, description="Maximum tool calls per execution")
    current_tool_calls: int = Field(default=0)
    
    async def process(self, task: Task) -> Result:
        """Process a task by executing it with tools.
        
        Args:
            task: The task or step to execute
            
        Returns:
            Result of the execution
        """
        self.context.add_message("system", "Executing task")
        self.context.add_message("user", task.description)
        
        self.current_step = 0
        self.current_tool_calls = 0
        
        # Execute steps until completion or max steps reached
        while await self.step() and self.current_step < self.max_steps:
            self.current_step += 1
        
        # Collect final results
        execution_summary = self._generate_summary()
        
        return Result(
            task_id=task.id,
            content=execution_summary,
            metadata={
                "steps_executed": self.current_step,
                "tool_calls": self.current_tool_calls
            },
            status="success" if self.current_step < self.max_steps else "incomplete"
        )
    
    async def step(self) -> bool:
        """Execute a single step of task execution.
        
        Returns:
            True if processing should continue, False if completed
        """
        # Check if we've reached execution limits
        if self.current_tool_calls >= self.max_tool_calls:
            self.context.add_message("system", "Reached maximum tool call limit")
            return False
        
        # Get execution decision from LLM
        decision = await self._get_next_action()
        
        # If decision indicates completion, stop execution
        if "task complete" in decision.get("content", "").lower():
            return False
            
        # Execute tool if specified
        tool_call = self._extract_tool_call(decision.get("content", ""))
        if tool_call:
            result = await self._execute_tool(tool_call)
            self.context.add_message("system", f"Tool result: {result}")
            self.current_tool_calls += 1
            return True
        
        # No valid action, but no completion indicator - continue
        return True
    
    async def _get_next_action(self) -> Dict[str, Any]:
        """Determine the next action to take using the LLM.
        
        Returns:
            Decision dict containing the next action
        """
        # Prepare context for decision
        tool_descriptions = "\n".join([
            f"- {tool.name}: {tool.description}" 
            for tool in self.tools.get_all_tools()
        ])
        
        # Get all context messages
        messages = self.context.get_recent_messages(10)
        
        # Add system instruction with available tools
        messages.insert(0, {
            "role": "system",
            "content": f"""You are an AI assistant tasked with executing a specific task.
            You have access to these tools: {tool_descriptions}
            
            Decide the next step to take. If you need to use a tool, format your response as:
            TOOL: [tool_name]
            PARAMS: [JSON formatted parameters]
            
            If you've completed the task, clearly state: TASK COMPLETE
            """
        })
        
        # Get decision from LLM
        response = await self.tools.get_tool("llm").execute({
            "messages": messages
        })
        
        return response
    
    def _extract_tool_call(self, decision_text: str) -> Optional[Dict[str, Any]]:
        """Extract tool call information from decision text.
        
        Args:
            decision_text: The text containing tool call instructions
            
        Returns:
            Tool call dict or None if no tool call found
        """
        if "TOOL:" not in decision_text:
            return None
            
        try:
            # Extract tool name
            tool_line = [line for line in decision_text.split("\n") if "TOOL:" in line][0]
            tool_name = tool_line.split("TOOL:")[1].strip()
            
            # Extract parameters
            params_line = [line for line in decision_text.split("\n") if "PARAMS:" in line][0]
            params_text = params_line.split("PARAMS:")[1].strip()
            
            # Parse parameters - in real implementation use json.loads
            # Simple parsing for demonstration
            params = {}
            if params_text.startswith("{") and params_text.endswith("}"):
                param_parts = params_text[1:-1].split(",")
                for part in param_parts:
                    if ":" in part:
                        k, v = part.split(":", 1)
                        params[k.strip().strip('"\'').strip()] = v.strip().strip('"\'').strip()
            
            return {
                "tool": tool_name,
                "params": params
            }
        except (IndexError, ValueError):
            return None
    
    async def _execute_tool(self, tool_call: Dict[str, Any]) -> Any:
        """Execute a tool with the given parameters.
        
        Args:
            tool_call: Dict containing tool name and parameters
            
        Returns:
            Result of tool execution
        """
        tool_name = tool_call.get("tool")
        params = tool_call.get("params", {})
        
        if not self.tools.has_tool(tool_name):
            return f"Error: Tool '{tool_name}' not found"
        
        try:
            result = await self.tools.get_tool(tool_name).execute(params)
            return result
        except Exception as e:
            return f"Error executing tool: {str(e)}"
    
    def _generate_summary(self) -> str:
        """Generate an execution summary based on context.
        
        Returns:
            Summary text
        """
        # Get all the messages for summarization
        messages = self.context.get_all_messages()
        
        # Extract user instructions and tool results
        instructions = []
        tool_results = []
        
        for msg in messages:
            if msg["role"] == "user":
                instructions.append(msg["content"])
            elif msg["role"] == "system" and "Tool result" in msg["content"]:
                tool_results.append(msg["content"])
        
        # Format summary
        summary = f"Execution Summary\n===============\n\n"
        summary += f"Task: {instructions[0] if instructions else 'Unknown'}\n\n"
        summary += f"Steps Taken: {self.current_step}\n"
        summary += f"Tools Used: {self.current_tool_calls}\n\n"
        
        if tool_results:
            summary += "Key Results:\n"
            for i, result in enumerate(tool_results[-3:]):  # Last 3 results
                summary += f"- {result}\n"
        
        return summary