from app.config.settings import get_settings

def test_config() :
    settings = get_settings()
    print("配置加载成功!")
    print(f"LLM提供商: {settings.llm.provider}")
    print(f"LLM基础URL: {settings.llm.base_url}")
    print(f"沙盒镜像: {settings.sandbox.image}")
    return settings

if __name__ == "__main__":
    test_config()
