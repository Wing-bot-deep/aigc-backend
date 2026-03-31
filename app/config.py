import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # LLM（OpenAI 兼容格式）
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o")

    # 图片生成后端: mock | dalle3 | comfyui
    IMAGE_BACKEND: str = os.getenv("IMAGE_BACKEND", "mock")
    COMFYUI_URL: str = os.getenv("COMFYUI_URL", "http://localhost:8188")

    # 质量控制
    QUALITY_THRESHOLD: float = float(os.getenv("QUALITY_THRESHOLD", "7.0"))

    # 服务
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))


settings = Settings()
