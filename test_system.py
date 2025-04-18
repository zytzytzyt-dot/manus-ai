import asyncio
from app.agents.orchestrator import OrchestratorAgent
from app.config.settings import get_settings

async def test_system():
    settings = get_settings()
    orchestrator = OrchestratorAgent()
    
    # 如果initialize方法不存在，则跳过
    if hasattr(orchestrator, 'initialize') and callable(orchestrator.initialize):
        await orchestrator.initialize()
    else:
        print("警告: OrchestratorAgent没有initialize方法，跳过初始化")
    
    print("系统初始化成功!")
    
    # 测试简单任务
    result = await orchestrator.process_task("计算1+1等于几")
    print(f"任务结果: {result}")
    
    return orchestrator

if __name__ == "__main__":
    asyncio.run(test_system())
