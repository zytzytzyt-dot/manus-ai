from app.tools import get_tool_registry

def test_tools():
    registry = get_tool_registry()
    print(f"已注册工具数量: {len(registry.tools)}")
    for name, tool in registry.tools.items():
        print(f"- {name}: {tool.description}")
    return registry

if __name__ == "__main__":
    test_tools()
