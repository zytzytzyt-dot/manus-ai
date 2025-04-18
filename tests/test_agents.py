import pytest
import asyncio
from unittest.mock import MagicMock, patch
from app.agents.orchestrator import OrchestratorAgent
from app.agents.planner import PlannerAgent
from app.agents.executor import ExecutorAgent
from app.agents.validator import ValidatorAgent
from app.models.task import Task
from app.models.result import Result
from app.models.plan import Plan

@pytest.fixture
def mock_llm():
    """模拟LLM客户端"""
    llm = MagicMock()
    llm.generate_response.return_value = asyncio.Future()
    llm.generate_response.return_value.set_result("模拟LLM响应")
    return llm

@pytest.fixture
def mock_executor():
    """模拟执行代理"""
    executor = MagicMock(spec=ExecutorAgent)
    future = asyncio.Future()
    future.set_result(Result(content="执行结果"))
    executor.execute.return_value = future
    return executor

@pytest.fixture
def mock_planner():
    """模拟规划代理"""
    planner = MagicMock(spec=PlannerAgent)
    future = asyncio.Future()
    future.set_result(Plan(steps=["步骤1", "步骤2", "步骤3"]))
    planner.create_plan.return_value = future
    return planner

@pytest.fixture
def mock_validator():
    """模拟验证代理"""
    validator = MagicMock(spec=ValidatorAgent)
    future = asyncio.Future()
    future.set_result(True)
    validator.validate.return_value = future
    return validator

@pytest.mark.asyncio
async def test_planner_create_plan(mock_llm):
    """测试规划代理创建计划"""
    # 设置
    planner = PlannerAgent(llm=mock_llm)
    task = Task(description="测试任务")
    
    # 执行
    plan = await planner.create_plan(task)
    
    # 验证
    assert isinstance(plan, Plan)
    assert len(plan.steps) > 0
    mock_llm.generate_response.assert_called_once()

@pytest.mark.asyncio
async def test_executor_execute(mock_llm):
    """测试执行代理执行任务"""
    # 设置
    executor = ExecutorAgent(llm=mock_llm)
    task = Task(description="测试任务")
    plan = Plan(steps=["步骤1", "步骤2"])
    
    # 执行
    result = await executor.execute(task, plan)
    
    # 验证
    assert isinstance(result, Result)
    assert result.content
    mock_llm.generate_response.assert_called()

@pytest.mark.asyncio
async def test_validator_validate(mock_llm):
    """测试验证代理验证结果"""
    # 设置
    validator = ValidatorAgent(llm=mock_llm)
    task = Task(description="测试任务")
    result = Result(content="测试结果")
    
    # 执行
    is_valid = await validator.validate(task, result)
    
    # 验证
    assert isinstance(is_valid, bool)
    mock_llm.generate_response.assert_called_once()

@pytest.mark.asyncio
async def test_orchestrator_process(mock_executor, mock_planner, mock_validator):
    """测试编排代理的处理流程"""
    # 设置
    orchestrator = OrchestratorAgent()
    orchestrator._executor = mock_executor
    orchestrator._planner = mock_planner
    orchestrator._validator = mock_validator
    
    task = Task(description="测试任务")
    
    # 执行
    result = await orchestrator.process(task)
    
    # 验证
    assert isinstance(result, Result)
    assert result.content == "执行结果"
    mock_planner.create_plan.assert_called_once()
    mock_executor.execute.assert_called_once()
    mock_validator.validate.assert_called_once()

@pytest.mark.asyncio
async def test_orchestrator_process_retry(mock_executor, mock_planner, mock_validator):
    """测试编排代理的重试流程"""
    # 设置
    orchestrator = OrchestratorAgent(max_attempts=2)
    orchestrator._executor = mock_executor
    orchestrator._planner = mock_planner
    orchestrator._validator = mock_validator
    
    # 第一次验证失败，第二次成功
    first_validation = asyncio.Future()
    first_validation.set_result(False)
    second_validation = asyncio.Future()
    second_validation.set_result(True)
    mock_validator.validate.side_effect = [first_validation, second_validation]
    
    task = Task(description="测试任务")
    
    # 执行
    result = await orchestrator.process(task)
    
    # 验证
    assert isinstance(result, Result)
    assert result.content == "执行结果"
    assert mock_planner.create_plan.call_count == 2
    assert mock_executor.execute.call_count == 2
    assert mock_validator.validate.call_count == 2
