"""HiveFlow Studio - 快速测试验证脚本 (绕过 sandbox 限制)"""
import asyncio
import sys
import os
import io

# 修复 Windows GBK 编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.engine_service import EngineService, get_engine
from app.db.config import init_storage, close_storage, get_storage
from app.db.base import WorkflowRecord
from hiveflow import HiveFlow, HiveFlowConfig


async def test_engine_service():
    """测试引擎服务"""
    print("\n=== 测试引擎服务 ===")
    engine = EngineService(HiveFlowConfig())
    
    # 启动
    await engine.start()
    print("✅ 引擎启动成功")
    
    # 检查状态
    metrics = await engine.get_metrics()
    print(f"✅ 指标获取成功: active_agents={metrics.get('active_agents', 0)}")
    
    # 测试 Agent 注册
    await engine.create_agent(
        agent_id="test-agent-1",
        skills=["test_skill"],
        read_keys=["data:*"],
        write_keys=["result:*"],
        task_handler=lambda ecm, view: {"result": "ok"},
    )
    print("✅ Agent 注册成功")
    
    # 列出 Agent
    agents = await engine.list_agents()
    print(f"✅ Agent 列表: {len(agents)} 个 Agent")
    
    # 测试黑板操作
    await engine.set_key("test:key", {"value": "test_data"})
    print("✅ 黑板写入成功")
    
    value = await engine.get_key("test:key")
    print(f"✅ 黑板读取成功: {value}")
    
    # 关闭
    await engine.shutdown()
    print("✅ 引擎关闭成功")
    
    return True


async def test_storage():
    """测试存储"""
    print("\n=== 测试存储 ===")
    await init_storage()
    
    storage = get_storage()
    assert storage is not None, "存储未初始化"
    print("✅ 存储初始化成功")
    
    # 测试保存/获取工作流
    wf_id = f"test-wf-{os.getpid()}"
    workflow = WorkflowRecord(
        id=wf_id,
        name="Test Workflow",
        description="A test workflow",
        graph={"nodes": []},
        nodes=[{"id": "n1", "data": {"label": "Test"}}],
        edges=[],
        metadata={"version": 1},
    )
    
    await storage.create_workflow(workflow)
    print("✅ 工作流保存成功")
    
    result = await storage.get_workflow(wf_id)
    assert result is not None, "工作流未找到"
    assert result.name == "Test Workflow"
    print("✅ 工作流获取成功")
    
    # 测试删除
    await storage.delete_workflow(wf_id)
    result = await storage.get_workflow(wf_id)
    assert result is None, "工作流未删除"
    print("✅ 工作流删除成功")
    
    await close_storage()
    print("✅ 存储关闭成功")
    
    return True


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("HiveFlow Studio - 全面测试")
    print("=" * 60)
    
    results = {}
    
    try:
        results["引擎服务"] = await test_engine_service()
    except Exception as e:
        print(f"❌ 引擎服务测试失败: {e}")
        import traceback
        traceback.print_exc()
        results["引擎服务"] = False
    
    try:
        results["存储"] = await test_storage()
    except Exception as e:
        print(f"❌ 存储测试失败: {e}")
        import traceback
        traceback.print_exc()
        results["存储"] = False
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_name}: {status}")
    
    all_passed = all(results.values())
    print(f"\n总体结果: {'✅ 全部通过' if all_passed else '❌ 有失败'}")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
