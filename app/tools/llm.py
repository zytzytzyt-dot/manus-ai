from typing import Dict, Any, List, Optional
from app.tools.base import BaseTool
from app.llm import LLM, Message
from app.utils.logger import get_logger

logger = get_logger(__name__)

class LLMTool(BaseTool):
    """LLM工具，提供与语言模型交互的能力"""
    
    name = "llm"
    description = "与大型语言模型交互，获取文本生成、问答和分析能力"
    
    def __init__(self):
        """初始化LLM工具"""
        super().__init__()
        self.llm = LLM()
    
    async def execute(self, prompt: str, system_prompt: Optional[str] = None, 
                     messages: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """执行LLM请求
        
        Args:
            prompt: 用户提示文本
            system_prompt: 可选的系统提示
            messages: 可选的历史消息列表
            
        Returns:
            包含LLM响应的字典
        """
        try:
            # 准备消息
            msg_list = []
            
            # 添加历史消息
            if messages:
                for msg in messages:
                    msg_list.append(Message(**msg))
            
            # 添加当前提示
            msg_list.append(Message(role="user", content=prompt))
            
            # 准备系统消息
            system_msgs = None
            if system_prompt:
                system_msgs = [Message(role="system", content=system_prompt)]
            
            # 发送请求
            response = await self.llm.ask(msg_list, system_msgs)
            
            # 返回结果
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
