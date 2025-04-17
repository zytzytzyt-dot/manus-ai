from typing import Dict, List, Optional, Union, Any

from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    """Configuration for a specific LLM model."""
    
    name: str = Field(..., description="Model name (e.g., gpt-4o, claude-3, etc.)")
    provider: str = Field(..., description="Model provider (e.g., openai, anthropic, etc.)")
    api_version: Optional[str] = Field(None, description="API version")
    api_type: Optional[str] = Field(None, description="API type")
    base_url: Optional[str] = Field(None, description="API base URL")
    max_tokens: int = Field(default=4096, description="Maximum tokens")
    context_window: int = Field(default=8192, description="Context window size")
    supports_vision: bool = Field(default=False, description="Whether model supports vision")
    supports_function_calling: bool = Field(default=True, description="Whether model supports function calling")
    token_limit: int = Field(default=16384, description="Token limit")
    pricing: Dict[str, float] = Field(default_factory=dict, description="Pricing information")
    capabilities: List[str] = Field(default_factory=list, description="Model capabilities")
    default_parameters: Dict[str, Any] = Field(default_factory=dict, description="Default parameters")
    
    @property
    def is_vision_model(self) -> bool:
        """Check if model supports vision."""
        return self.supports_vision or "vision" in self.capabilities
    
    @property
    def can_call_functions(self) -> bool:
        """Check if model supports function calling."""
        return self.supports_function_calling or "function_calling" in self.capabilities


class ModelRegistry(BaseModel):
    """Registry of available LLM models."""
    
    models: Dict[str, ModelConfig] = Field(default_factory=dict, description="Available models")
    default_model: str = Field(default="gpt-4o", description="Default model")
    
    def register_model(self, model: ModelConfig) -> None:
        """Register a model.
        
        Args:
            model: Model configuration
        """
        self.models[model.name] = model
    
    def get_model(self, model_name: Optional[str] = None) -> ModelConfig:
        """Get a model configuration.
        
        Args:
            model_name: Model name or None for default
            
        Returns:
            Model configuration
            
        Raises:
            ValueError: If model not found
        """
        name = model_name or self.default_model
        if name not in self.models:
            raise ValueError(f"Model '{name}' not found in registry")
        return self.models[name]
    
    def get_models_by_provider(self, provider: str) -> List[ModelConfig]:
        """Get models by provider.
        
        Args:
            provider: Provider name
            
        Returns:
            List of matching models
        """
        return [model for model in self.models.values() if model.provider == provider]
    
    def get_models_with_capability(self, capability: str) -> List[ModelConfig]:
        """Get models with a specific capability.
        
        Args:
            capability: Capability to look for
            
        Returns:
            List of matching models
        """
        return [
            model for model in self.models.values() 
            if capability in model.capabilities
        ]
    
    def get_best_model_for_task(self, task_type: str) -> ModelConfig:
        """Get the best model for a specific task type.
        
        Args:
            task_type: Task type (e.g., 'vision', 'code', 'text', etc.)
            
        Returns:
            Best matching model
            
        Raises:
            ValueError: If no suitable model found
        """
        # Task type to capability mapping
        task_capability_map = {
            "vision": "vision",
            "code": "code_generation",
            "reasoning": "reasoning",
            "factual": "facts",
            "creative": "creative",
            "function_calling": "function_calling"
        }
        
        capability = task_capability_map.get(task_type)
        if not capability:
            return self.get_model(self.default_model)
            
        # Find models with this capability
        matching_models = self.get_models_with_capability(capability)
        
        if not matching_models:
            # Fall back to default model
            return self.get_model(self.default_model)
            
        # Sort by context window size (larger is better)
        matching_models.sort(key=lambda m: m.context_window, reverse=True)
        
        return matching_models[0]


# Initialize model registry with common models
def create_model_registry() -> ModelRegistry:
    """Create and initialize model registry with common models.
    
    Returns:
        Initialized model registry
    """
    registry = ModelRegistry()
    
    # OpenAI models
    registry.register_model(ModelConfig(
        name="gpt-4o",
        provider="openai",
        max_tokens=4096,
        context_window=128000,
        supports_vision=True,
        supports_function_calling=True,
        token_limit=128000,
        pricing={"input": 0.000005, "output": 0.000015},
        capabilities=["vision", "reasoning", "facts", "creative", "function_calling", "code_generation"],
        default_parameters={"temperature": 0.7}
    ))
    
    registry.register_model(ModelConfig(
        name="gpt-4-turbo",
        provider="openai",
        max_tokens=4096,
        context_window=128000,
        supports_vision=True,
        supports_function_calling=True,
        token_limit=128000,
        pricing={"input": 0.00001, "output": 0.00003},
        capabilities=["vision", "reasoning", "facts", "creative", "function_calling", "code_generation"],
        default_parameters={"temperature": 0.7}
    ))
    
    registry.register_model(ModelConfig(
        name="gpt-3.5-turbo",
        provider="openai",
        max_tokens=4096,
        context_window=16385,
        supports_vision=False,
        supports_function_calling=True,
        token_limit=16385,
        pricing={"input": 0.0000005, "output": 0.0000015},
        capabilities=["reasoning", "facts", "creative", "function_calling", "code_generation"],
        default_parameters={"temperature": 0.7}
    ))
    
    # Anthropic models
    registry.register_model(ModelConfig(
        name="claude-3-opus",
        provider="anthropic",
        max_tokens=4096,
        context_window=200000,
        supports_vision=True,
        supports_function_calling=True,
        token_limit=200000,
        pricing={"input": 0.00001, "output": 0.00003},
        capabilities=["vision", "reasoning", "facts", "creative", "function_calling", "code_generation"],
        default_parameters={"temperature": 0.7}
    ))
    
    registry.register_model(ModelConfig(
        name="claude-3-sonnet",
        provider="anthropic",
        max_tokens=4096,
        context_window=200000,
        supports_vision=True,
        supports_function_calling=True,
        token_limit=200000,
        pricing={"input": 0.000003, "output": 0.000015},
        capabilities=["vision", "reasoning", "facts", "creative", "function_calling", "code_generation"],
        default_parameters={"temperature": 0.7}
    ))
    
    return registry


# Global model registry instance
MODEL_REGISTRY = create_model_registry()