import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # LLM
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-sonnet-4-6")

    # 图片生成后端: mock | dalle3 | comfyui
    IMAGE_BACKEND: str = os.getenv("IMAGE_BACKEND", "mock")
    COMFYUI_URL: str = os.getenv("COMFYUI_URL", "http://localhost:8188")

    # 质量控制
    QUALITY_THRESHOLD: float = float(os.getenv("QUALITY_THRESHOLD", "7.0"))

    # 服务
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))


settings = Settings()
