import asyncio
import argparse
import os
import sys
from typing import Optional

from app.agents.orchestrator import OrchestratorAgent
from app.models.task import Task
from app.utils.logger import configure_logging, get_logger
from app.utils.error_handling import setup_global_exception_handler
from app.config.settings import get_settings
from app.ui.server import APIServer

# Initialize logger
logger = get_logger(__name__)

async def run_task(description: str, agent_type: Optional[str] = None) -> None:
    """Run a task using the specified agent.
    
    Args:
        description: Task description
        agent_type: Agent type to use (default: Orchestrator)
    """
    # Create orchestrator
    orchestrator = OrchestratorAgent()
    
    # Create task
    task = Task(description=description)
    
    logger.info(f"Processing task: {description}")
    
    # Process task
    try:
        result = await orchestrator.process(task)
        
        # Print result
        print("\n" + "="*80)
        print("Task Result:")
        print("="*80)
        print(result.content)
        print("="*80)
        
    except Exception as e:
        logger.error(f"Error processing task: {str(e)}")
        print(f"\nError: {str(e)}")

async def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the API server.
    
    Args:
        host: Host address
        port: Port number
    """
    server = APIServer()
    await server.start(host, port)

async def main() -> None:
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Manus-AI: Multi-agent AI System")
    
    # Add subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Task command
    task_parser = subparsers.add_parser("task", help="Run a task")
    task_parser.add_argument("description", help="Task description")
    task_parser.add_argument("--agent", help="Agent type to use")
    
    # Server command
    server_parser = subparsers.add_parser("server", help="Start the API server")
    server_parser.add_argument("--host", default="0.0.0.0", help="Host address")
    server_parser.add_argument("--port", type=int, default=8000, help="Port number")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Configure logging
    configure_logging()
    
    # Set up global exception handler
    setup_global_exception_handler()
    
    # Load settings
    settings = get_settings()
    
    # Create workspace directory if it doesn't exist
    os.makedirs(settings.workspace_dir, exist_ok=True)
    
    # Execute command
    if args.command == "task":
        await run_task(args.description, args.agent)
    elif args.command == "server":
        await run_server(args.host, args.port)
    else:
        # Default behavior: interactive prompt
        print("Manus-AI: Multi-agent AI System")
        print("Enter your task or type 'exit' to quit.")
        
        while True:
            try:
                prompt = input("\nEnter your task: ")
                if not prompt:
                    continue
                    
                if prompt.lower() in ["exit", "quit"]:
                    break
                    
                await run_task(prompt)
                
            except KeyboardInterrupt:
                print("\nOperation interrupted.")
                break
                
            except Exception as e:
                logger.error(f"Error: {str(e)}")
                print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())