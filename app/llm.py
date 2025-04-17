import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Union, Literal

import aiohttp
from pydantic import BaseModel, Field, model_validator

from app.config.settings import get_settings
from app.config.model_config import MODEL_REGISTRY
from app.utils.logger import get_logger
from app.utils.error_handling import handle_exceptions

# Set up logger
logger = get_logger(__name__)

class TokenLimitExceeded(Exception):
    """Raised when a token limit is exceeded."""
    pass

class Message(BaseModel):
    """Message for LLM conversation."""
    
    role: str = Field(..., description="Message role")
    content: Optional[str] = Field(None, description="Message content")
    name: Optional[str] = Field(None, description="Name for function calling")
    tool_call_id: Optional[str] = Field(None, description="Tool call ID")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Tool calls")
    base64_image: Optional[str] = Field(None, description="Base64 encoded image")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to API format dictionary."""
        result = {"role": self.role}
        
        if self.content is not None:
            # Handle image content
            if self.base64_image:
                result["content"] = [
                    {"type": "text", "text": self.content or ""},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{self.base64_image}"
                        }
                    }
                ]
            else:
                result["content"] = self.content
                
        if self.name is not None:
            result["name"] = self.name
            
        if self.tool_call_id is not None:
            result["tool_call_id"] = self.tool_call_id
            
        if self.tool_calls is not None:
            result["tool_calls"] = self.tool_calls
            
        return result

class LLMResponse(BaseModel):
    """Response from LLM."""
    
    content: Optional[str] = None
    tool_calls: Optional[List[Any]] = None
    finish_reason: Optional[str] = None
    
    @property
    def is_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return bool(self.tool_calls)

class LLM:
    """Interface for interacting with LLMs."""
    
    def __init__(self, config_name: str = None):
        """Initialize LLM client.
        
        Args:
            config_name: Configuration section name
        """
        self.settings = get_settings()
        
        # Get LLM configuration
        if config_name == "vision":
            self.config = self.settings.vision_llm or self.settings.llm
        else:
            self.config = self.settings.llm
            
        # API configuration
        self.api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("No API key provided for LLM")
            
        self.base_url = self.config.base_url
        self.model = self.config.model
        self.max_tokens = self.config.max_tokens
        self.temperature = self.config.temperature
        
        # Get model information
        try:
            self.model_info = MODEL_REGISTRY.get_model(self.model)
        except Exception:
            # Use default if model not in registry
            self.model_info = None
    
    @handle_exceptions(
        error_classes={
            aiohttp.ClientError: "API connection error",
            json.JSONDecodeError: "Invalid API response",
            TokenLimitExceeded: "Token limit exceeded"
        },
        default_message="LLM request failed",
        log_error=True,
        reraise=True
    )
    async def ask(
        self, 
        messages: Union[List[Dict], List[Message]], 
        system_msgs: Optional[Union[List[Dict], List[Message]]] = None
    ) -> LLMResponse:
        """Send a completion request to the LLM.
        
        Args:
            messages: List of conversation messages
            system_msgs: Optional system messages
            
        Returns:
            LLM response
            
        Raises:
            Exception: If request fails
        """
        # Prepare messages
        prepped_msgs = []
        
        # Add system messages
        if system_msgs:
            for msg in system_msgs:
                if isinstance(msg, Message):
                    prepped_msgs.append(msg.to_dict())
                else:
                    prepped_msgs.append(msg)
        
        # Add user messages
        for msg in messages:
            if isinstance(msg, Message):
                prepped_msgs.append(msg.to_dict())
            else:
                prepped_msgs.append(msg)
        
        # Prepare request payload
        payload = {
            "model": self.model,
            "messages": prepped_msgs,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
        
        logger.debug(f"Sending request to LLM: {json.dumps(payload, indent=2)}")
        
        # Make API request
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    # Check for token limit error
                    if "maximum context length" in error_text:
                        raise TokenLimitExceeded(error_text)
                    raise Exception(f"API request failed with status {response.status}: {error_text}")
                
                data = await response.json()
                
                try:
                    content = data["choices"][0]["message"].get("content")
                    tool_calls = data["choices"][0]["message"].get("tool_calls")
                    finish_reason = data["choices"][0].get("finish_reason")
                    
                    return LLMResponse(
                        content=content,
                        tool_calls=tool_calls,
                        finish_reason=finish_reason
                    )
                except (KeyError, IndexError) as e:
                    logger.error(f"Error parsing LLM response: {e}")
                    logger.debug(f"Full response: {data}")
                    raise Exception(f"Failed to parse LLM response: {e}")
    
    @handle_exceptions(
        error_classes={
            aiohttp.ClientError: "API connection error",
            json.JSONDecodeError: "Invalid API response",
            TokenLimitExceeded: "Token limit exceeded"
        },
        default_message="LLM tool request failed",
        log_error=True,
        reraise=True
    )
    async def ask_tool(
        self,
        messages: Union[List[Dict], List[Message]],
        tools: List[Dict],
        system_msgs: Optional[Union[List[Dict], List[Message]]] = None,
        tool_choice: Literal["none", "auto", "required"] = "auto"
    ) -> LLMResponse:
        """Send a function-calling request to the LLM.
        
        Args:
            messages: List of conversation messages
            tools: List of tool definitions
            system_msgs: Optional system messages
            tool_choice: Tool choice strategy
            
        Returns:
            LLM response
            
        Raises:
            Exception: If request fails
        """
        # Prepare messages
        prepped_msgs = []
        
        # Add system messages
        if system_msgs:
            for msg in system_msgs:
                if isinstance(msg, Message):
                    prepped_msgs.append(msg.to_dict())
                else:
                    prepped_msgs.append(msg)
        
        # Add user messages
        for msg in messages:
            if isinstance(msg, Message):
                prepped_msgs.append(msg.to_dict())
            else:
                prepped_msgs.append(msg)
        
        # Prepare request payload
        payload = {
            "model": self.model,
            "messages": prepped_msgs,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "tools": tools
        }
        
        # Handle tool choice strategy
        if tool_choice == "none":
            payload["tool_choice"] = "none"
        elif tool_choice == "required":
            payload["tool_choice"] = "required"
        else:
            payload["tool_choice"] = "auto"
        
        logger.debug(f"Sending tool request to LLM: {json.dumps(payload, indent=2)}")
        
        # Make API request
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    # Check for token limit error
                    if "maximum context length" in error_text:
                        raise TokenLimitExceeded(error_text)
                    raise Exception(f"API request failed with status {response.status}: {error_text}")
                
                data = await response.json()
                
                try:
                    msg = data["choices"][0]["message"]
                    content = msg.get("content")
                    tool_calls = msg.get("tool_calls")
                    finish_reason = data["choices"][0].get("finish_reason")
                    
                    return LLMResponse(
                        content=content,
                        tool_calls=tool_calls,
                        finish_reason=finish_reason
                    )
                except (KeyError, IndexError) as e:
                    logger.error(f"Error parsing LLM response: {e}")
                    logger.debug(f"Full response: {data}")
                    raise Exception(f"Failed to parse LLM response: {e}")