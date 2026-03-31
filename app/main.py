"""
FastAPI 应用入口
启动方式：
  开发：python -m app.main
  生产：uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import settings

app = FastAPI(
    title="蓝色光标 AIGC 营销素材生成服务",
    description=(
        "基于 LangGraph 的智能营销素材后端。\n\n"
        "核心能力：\n"
        "- 根据品牌信息自动生成优化的图片提示词\n"
        "- 支持 DALL-E 3 / 本地 Flux/SDXL (ComfyUI) 图片生成\n"
        "- LLM-as-Judge 自动质检，不合格则带反馈重试\n"
        "- 异步任务队列，支持高并发请求\n"
    ),
    version="1.0.0",
    docs_url="/docs",       # Swagger UI
    redoc_url="/redoc",     # ReDoc
)

# ── CORS（允许前端/小程序跨域调用）────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 生产环境替换为具体域名，如 ["https://yourapp.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "蓝色光标 AIGC 营销素材生成服务",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,    # 开发模式热重载，生产环境去掉
    )
