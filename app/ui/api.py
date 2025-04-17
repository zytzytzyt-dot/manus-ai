from typing import Dict, List, Optional, Any
import json

from pydantic import BaseModel, Field


class APIEndpoint(BaseModel):
    """API endpoint specification."""
    
    path: str = Field(..., description="Endpoint path")
    method: str = Field(..., description="HTTP method")
    description: str = Field(..., description="Endpoint description")
    parameters: List[Dict[str, Any]] = Field(default_factory=list, description="Endpoint parameters")
    request_body: Optional[Dict[str, Any]] = Field(None, description="Request body schema")
    responses: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Response schemas")


class APISpec(BaseModel):
    """API specification."""
    
    title: str = Field(default="Manus-AI API", description="API title")
    description: str = Field(default="API for Manus-AI system", description="API description")
    version: str = Field(default="1.0.0", description="API version")
    base_path: str = Field(default="/api", description="API base path")
    endpoints: List[APIEndpoint] = Field(default_factory=list, description="API endpoints")
    
    def add_endpoint(self, endpoint: APIEndpoint) -> None:
        """Add an endpoint to the specification.
        
        Args:
            endpoint: Endpoint to add
        """
        self.endpoints.append(endpoint)
    
    def to_openapi(self) -> Dict[str, Any]:
        """Convert to OpenAPI specification.
        
        Returns:
            OpenAPI specification
        """
        paths = {}
        
        for endpoint in self.endpoints:
            path = endpoint.path
            method = endpoint.method.lower()
            
            if path not in paths:
                paths[path] = {}
                
            paths[path][method] = {
                'summary': endpoint.description,
                'description': endpoint.description,
                'parameters': endpoint.parameters,
                'responses': {
                    code: {
                        'description': schema.get('description', ''),
                        'content': {
                            'application/json': {
                                'schema': schema.get('schema', {})
                            }
                        }
                    }
                    for code, schema in endpoint.responses.items()
                }
            }
            
            if endpoint.request_body:
                paths[path][method]['requestBody'] = {
                    'content': {
                        'application/json': {
                            'schema': endpoint.request_body
                        }
                    }
                }
        
        return {
            'openapi': '3.0.0',
            'info': {
                'title': self.title,
                'description': self.description,
                'version': self.version
            },
            'paths': paths
        }
    
    def to_json(self) -> str:
        """Convert to JSON string.
        
        Returns:
            JSON string
        """
        return json.dumps(self.to_openapi(), indent=2)


# Create API specification
def create_api_spec() -> APISpec:
    """Create API specification.
    
    Returns:
        API specification
    """
    spec = APISpec()
    
    # Task endpoints
    spec.add_endpoint(APIEndpoint(
        path="/tasks",
        method="POST",
        description="Create a new task",
        request_body={
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Task description"
                },
                "priority": {
                    "type": "integer",
                    "description": "Task priority"
                },
                "tags": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Task tags"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata"
                }
            },
            "required": ["description"]
        },
        responses={
            "200": {
                "description": "Task created",
                "schema": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string"
                        },
                        "status": {
                            "type": "string"
                        }
                    }
                }
            },
            "400": {
                "description": "Bad request",
                "schema": {
                    "type": "object",
                    "properties": {
                        "error": {
                            "type": "string"
                        }
                    }
                }
            }
        }
    ))
    
    spec.add_endpoint(APIEndpoint(
        path="/tasks",
        method="GET",
        description="List tasks",
        parameters=[
            {
                "name": "limit",
                "in": "query",
                "description": "Maximum number of tasks to return",
                "schema": {
                    "type": "integer",
                    "default": 10
                }
            },
            {
                "name": "offset",
                "in": "query",
                "description": "Number of tasks to skip",
                "schema": {
                    "type": "integer",
                    "default": 0
                }
            },
            {
                "name": "status",
                "in": "query",
                "description": "Filter tasks by status",
                "schema": {
                    "type": "string"
                }
            },
            {
                "name": "tag",
                "in": "query",
                "description": "Filter tasks by tag",
                "schema": {
                    "type": "string"
                }
            }
        ],
        responses={
            "200": {
                "description": "Task list",
                "schema": {
                    "type": "object",
                    "properties": {
                        "tasks": {
                            "type": "array",
                            "items": {
                                "type": "object"
                            }
                        },
                        "total": {
                            "type": "integer"
                        },
                        "limit": {
                            "type": "integer"
                        },
                        "offset": {
                            "type": "integer"
                        }
                    }
                }
            }
        }
    ))
    
    spec.add_endpoint(APIEndpoint(
        path="/tasks/{task_id}",
        method="GET",
        description="Get a specific task",
        parameters=[
            {
                "name": "task_id",
                "in": "path",
                "required": True,
                "description": "Task ID",
                "schema": {
                    "type": "string"
                }
            }
        ],
        responses={
            "200": {
                "description": "Task details",
                "schema": {
                    "type": "object"
                }
            },
            "404": {
                "description": "Task not found",
                "schema": {
                    "type": "object",
                    "properties": {
                        "error": {
                            "type": "string"
                        }
                    }
                }
            }
        }
    ))
    
    # Result endpoints
    spec.add_endpoint(APIEndpoint(
        path="/results/{result_id}",
        method="GET",
        description="Get a specific result",
        parameters=[
            {
                "name": "result_id",
                "in": "path",
                "required": True,
                "description": "Result ID",
                "schema": {
                    "type": "string"
                }
            }
        ],
        responses={
            "200": {
                "description": "Result details",
                "schema": {
                    "type": "object"
                }
            },
            "404": {
                "description": "Result not found",
                "schema": {
                    "type": "object",
                    "properties": {
                        "error": {
                            "type": "string"
                        }
                    }
                }
            }
        }
    ))
    
    return spec


# Global API specification
API_SPEC = create_api_spec()