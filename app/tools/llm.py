from typing import Dict, Any, List, Optional, ClassVar
from app.tools.base import BaseTool
from app.llm import LLM, Message
from app.utils.logger import get_logger
from pydantic import Field

logger = get_logger(__name__)

class LLMTool(BaseTool):
    
    name: ClassVar[str] = "llm"
    description: ClassVar[str] = "Interact with large language models to acquire text generation, question-answering and analysis capabilities"
    llm: Optional[LLM] = Field(default=None, exclude=True)

    def __init__(self):
        super().__init__()
        self.llm = LLM()
    
    async def execute(self, prompt: str, system_prompt: Optional[str] = None, 
                     messages: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:

        try:
            msg_list = []
            if messages:
                for msg in messages:
                    msg_list.append(Message(**msg))
            msg_list.append(Message(role="user", content=prompt))
            system_msgs = None
            if system_prompt:
                system_msgs = [Message(role="system", content=system_prompt)]
            
            response = await self.llm.ask(msg_list, system_msgs)
            
            return {
                "content": response.content,
                "tool_calls": response.tool_calls,
                "finish_reason": response.finish_reason
            }
            
        except Exception as e:
            logger.error(f"LLM工具执行失败: {str(e)}")
            return {
                "error": str(e),
                "content": "LLM请求处理过程中发生错误"
            }
    
    async def cleanup(self) -> None:
        """清理资源"""
        pass
