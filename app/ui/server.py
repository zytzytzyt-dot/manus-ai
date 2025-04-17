import asyncio
import json
import os
from typing import Dict, List, Optional, Any

from aiohttp import web
import aiohttp_cors

from app.agents.orchestrator import OrchestratorAgent
from app.models.task import Task
from app.utils.logger import get_logger
from app.config.settings import get_settings

# Set up logger
logger = get_logger(__name__)

class APIServer:
    """API server for the Manus-AI system.
    
    Provides HTTP API endpoints for system interaction.
    """
    def __init__(self):
        """Initialize the API server."""
        self.app = web.Application()
        self.settings = get_settings()
        self.orchestrator = OrchestratorAgent()
        self.tasks = {}
        self.results = {}
        
        # Configure CORS
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*"
            )
        })
        
        # Set up routes
        self.setup_routes()
        
        # Apply CORS to routes
        for route in list(self.app.router.routes()):
            cors.add(route)

    def setup_routes(self):
        """Set up API routes."""
        # Task management
        self.app.router.add_post('/api/tasks', self.create_task)
        self.app.router.add_get('/api/tasks', self.list_tasks)
        self.app.router.add_get('/api/tasks/{task_id}', self.get_task)
        self.app.router.add_delete('/api/tasks/{task_id}', self.delete_task)
        
        # Results
        self.app.router.add_get('/api/results/{result_id}', self.get_result)
        self.app.router.add_get('/api/tasks/{task_id}/results', self.get_task_results)
        
        # Tools and agents
        self.app.router.add_get('/api/tools', self.list_tools)
        self.app.router.add_get('/api/agents', self.list_agents)
        
        # System
        self.app.router.add_get('/api/status', self.get_status)
        
        # Static files
        self.app.router.add_static('/static', path=os.path.join(os.path.dirname(__file__), 'static'))
        self.app.router.add_get('/{path:.*}', self.serve_index)
    
    async def create_task(self, request: web.Request) -> web.Response:
        """Create a new task.
        
        Args:
            request: HTTP request
            
        Returns:
            HTTP response
        """
        try:
            data = await request.json()
            
            # Validate required fields
            if 'description' not in data:
                return web.json_response(
                    {'error': 'Task description is required'}, 
                    status=400
                )
            
            # Create task
            task = Task(
                description=data['description'],
                priority=data.get('priority', 0),
                tags=data.get('tags', []),
                metadata=data.get('metadata', {})
            )
            
            # Store task
            self.tasks[task.id] = task
            
            # Process task asynchronously
            asyncio.create_task(self._process_task(task))
            
            return web.json_response({
                'task_id': task.id,
                'status': 'created'
            })
            
        except Exception as e:
            logger.error(f"Error creating task: {str(e)}")
            return web.json_response(
                {'error': f'Failed to create task: {str(e)}'}, 
                status=500
            )
    
    async def list_tasks(self, request: web.Request) -> web.Response:
        """List all tasks.
        
        Args:
            request: HTTP request
            
        Returns:
            HTTP response
        """
        try:
            # Parse query parameters
            limit = int(request.query.get('limit', '10'))
            offset = int(request.query.get('offset', '0'))
            status = request.query.get('status')
            tag = request.query.get('tag')
            
            # Filter and sort tasks
            tasks = list(self.tasks.values())
            
            # Filter by status if provided
            if status:
                tasks = [t for t in tasks if t.metadata.get('status') == status]
                
            # Filter by tag if provided
            if tag:
                tasks = [t for t in tasks if tag in t.tags]
                
            # Sort by creation time (newest first)
            tasks.sort(key=lambda t: t.created_at, reverse=True)
            
            # Apply pagination
            paginated_tasks = tasks[offset:offset+limit]
            
            return web.json_response({
                'tasks': [t.dict() for t in paginated_tasks],
                'total': len(tasks),
                'limit': limit,
                'offset': offset
            })
            
        except Exception as e:
            logger.error(f"Error listing tasks: {str(e)}")
            return web.json_response(
                {'error': f'Failed to list tasks: {str(e)}'}, 
                status=500
            )
    
    async def get_task(self, request: web.Request) -> web.Response:
        """Get a specific task.
        
        Args:
            request: HTTP request
            
        Returns:
            HTTP response
        """
        try:
            task_id = request.match_info['task_id']
            
            if task_id not in self.tasks:
                return web.json_response(
                    {'error': 'Task not found'}, 
                    status=404
                )
                
            task = self.tasks[task_id]
            
            return web.json_response(task.dict())
            
        except Exception as e:
            logger.error(f"Error getting task: {str(e)}")
            return web.json_response(
                {'error': f'Failed to get task: {str(e)}'}, 
                status=500
            )
    
    async def delete_task(self, request: web.Request) -> web.Response:
        """Delete a task.
        
        Args:
            request: HTTP request
            
        Returns:
            HTTP response
        """
        try:
            task_id = request.match_info['task_id']
            
            if task_id not in self.tasks:
                return web.json_response(
                    {'error': 'Task not found'}, 
                    status=404
                )
                
            # Delete task
            del self.tasks[task_id]
            
            # Delete associated results
            self.results = {
                k: v for k, v in self.results.items() 
                if v.task_id != task_id
            }
            
            return web.json_response({'status': 'deleted'})
            
        except Exception as e:
            logger.error(f"Error deleting task: {str(e)}")
            return web.json_response(
                {'error': f'Failed to delete task: {str(e)}'}, 
                status=500
            )
    
    async def get_result(self, request: web.Request) -> web.Response:
        """Get a specific result.
        
        Args:
            request: HTTP request
            
        Returns:
            HTTP response
        """
        try:
            result_id = request.match_info['result_id']
            
            # Find result
            result = None
            for r in self.results.values():
                if r.id == result_id:
                    result = r
                    break
                    
            if not result:
                return web.json_response(
                    {'error': 'Result not found'}, 
                    status=404
                )
                
            return web.json_response(result.dict())
            
        except Exception as e:
            logger.error(f"Error getting result: {str(e)}")
            return web.json_response(
                {'error': f'Failed to get result: {str(e)}'}, 
                status=500
            )
    
    async def get_task_results(self, request: web.Request) -> web.Response:
        """Get results for a specific task.
        
        Args:
            request: HTTP request
            
        Returns:
            HTTP response
        """
        try:
            task_id = request.match_info['task_id']
            
            if task_id not in self.tasks:
                return web.json_response(
                    {'error': 'Task not found'}, 
                    status=404
                )
                
            # Get results for task
            task_results = [
                r.dict() for r in self.results.values() 
                if r.task_id == task_id
            ]
            
            return web.json_response({
                'task_id': task_id,
                'results': task_results
            })
            
        except Exception as e:
            logger.error(f"Error getting task results: {str(e)}")
            return web.json_response(
                {'error': f'Failed to get task results: {str(e)}'}, 
                status=500
            )
    
    async def list_tools(self, request: web.Request) -> web.Response:
        """List available tools.
        
        Args:
            request: HTTP request
            
        Returns:
            HTTP response
        """
        try:
            # Get tools from orchestrator
            tools = self.orchestrator.tools.get_tool_schemas()
            
            return web.json_response({
                'tools': tools
            })
            
        except Exception as e:
            logger.error(f"Error listing tools: {str(e)}")
            return web.json_response(
                {'error': f'Failed to list tools: {str(e)}'}, 
                status=500
            )
    
    async def list_agents(self, request: web.Request) -> web.Response:
        """List available agents.
        
        Args:
            request: HTTP request
            
        Returns:
            HTTP response
        """
        try:
            # Get agents from orchestrator
            agents = [
                {
                    'name': agent.name,
                    'description': agent.description
                }
                for agent in self.orchestrator.agent_registry.get_all()
            ]
            
            return web.json_response({
                'agents': agents
            })
            
        except Exception as e:
            logger.error(f"Error listing agents: {str(e)}")
            return web.json_response(
                {'error': f'Failed to list agents: {str(e)}'}, 
                status=500
            )
    
    async def get_status(self, request: web.Request) -> web.Response:
        """Get system status.
        
        Args:
            request: HTTP request
            
        Returns:
            HTTP response
        """
        try:
            return web.json_response({
                'status': 'running',
                'version': '1.0.0',
                'tasks': len(self.tasks),
                'results': len(self.results),
                'uptime_seconds': 0  # TODO: Implement uptime tracking
            })
            
        except Exception as e:
            logger.error(f"Error getting status: {str(e)}")
            return web.json_response(
                {'error': f'Failed to get status: {str(e)}'}, 
                status=500
            )
    
    async def serve_index(self, request: web.Request) -> web.Response:
        """Serve the index HTML file.
        
        Args:
            request: HTTP request
            
        Returns:
            HTTP response
        """
        try:
            index_path = os.path.join(
                os.path.dirname(__file__), 
                'static', 
                'index.html'
            )
            
            if os.path.exists(index_path):
                return web.FileResponse(index_path)
            else:
                return web.Response(
                    text="UI not found. Run 'npm run build' in the ui directory.",
                    content_type='text/plain'
                )
                
        except Exception as e:
            logger.error(f"Error serving index: {str(e)}")
            return web.Response(
                text=f"Error: {str(e)}",
                content_type='text/plain',
                status=500
            )
    
    async def _process_task(self, task: Task) -> None:
        """Process a task using the orchestrator.
        
        Args:
            task: Task to process
        """
        try:
            # Update task status
            task.metadata['status'] = 'processing'
            
            # Process task
            result = await self.orchestrator.process(task)
            
            # Store result
            self.results[result.id] = result
            
            # Update task status
            task.metadata['status'] = 'completed'
            task.metadata['result_id'] = result.id
            
        except Exception as e:
            logger.error(f"Error processing task: {str(e)}")
            
            # Update task status
            task.metadata['status'] = 'failed'
            task.metadata['error'] = str(e)
    
    async def start(self, host: str = '0.0.0.0', port: int = 8000) -> None:
        """Start the API server.
        
        Args:
            host: Host address
            port: Port number
        """
        # Initialize orchestrator
        await self.orchestrator.initialize()
        
        # Start server
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        logger.info(f"API server started on http://{host}:{port}")
        
        # Keep server running
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
    
    def run(self, host: str = '0.0.0.0', port: int = 8000) -> None:
        """Run the API server synchronously.
        
        Args:
            host: Host address
            port: Port number
        """
        web.run_app(self.app, host=host, port=port)
