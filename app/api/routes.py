"""
FastAPI 路由
POST /api/v1/generate     提交素材生成任务（异步，立即返回 task_id）
GET  /api/v1/tasks/{id}   查询任务状态和结果
GET  /api/v1/health       健康检查
"""
import uuid
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from ..graph.workflow import workflow
from ..config import settings

router = APIRouter(prefix="/api/v1", tags=["AIGC营销素材"])

# ── 简单内存任务存储（生产环境替换为 Redis）────────────────────────────────────
_tasks: Dict[str, Dict[str, Any]] = {}


# ── 请求/响应模型 ──────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    brand_name: str = Field(..., example="维达Tempo", description="品牌名称")
    brand_style: str = Field(..., example="莫兰迪色，白底轻奢", description="品牌视觉风格")
    product_name: str = Field(..., example="维达抽纸200抽", description="产品名称")
    product_description: str = Field(..., example="三层加厚，柔软亲肤，适合家用", description="产品描述")
    campaign_type: str = Field(..., example="小红书种草", description="投放场景")
    max_retries: int = Field(2, ge=0, le=5, description="最大重试次数（0-5）")


class TaskResult(BaseModel):
    image_urls: List[str]
    quality_score: float
    generated_prompt: str
    retry_count: int
    brand_name: str
    product_name: str


class TaskResponse(BaseModel):
    task_id: str
    status: str               # queued | running | completed | failed
    result: Optional[TaskResult] = None
    error: Optional[str] = None


# ── 后台任务执行函数 ───────────────────────────────────────────────────────────

def _run_workflow(task_id: str, initial_state: dict) -> None:
    """在 FastAPI BackgroundTasks 线程中同步运行 LangGraph 工作流"""
    try:
        _tasks[task_id]["status"] = "running"
        final_state = workflow.invoke(initial_state)
        _tasks[task_id] = {
            "status": "completed",
            "result": {
                "image_urls": final_state.get("image_urls", []),
                "quality_score": final_state.get("quality_score", 0.0),
                "generated_prompt": final_state.get("generated_prompt", ""),
                "retry_count": final_state.get("retry_count", 0),
                "brand_name": final_state.get("brand_name", ""),
                "product_name": final_state.get("product_name", ""),
            },
            "error": None,
        }
    except Exception as e:
        _tasks[task_id] = {
            "status": "failed",
            "result": None,
            "error": str(e),
        }


# ── API 端点 ──────────────────────────────────────────────────────────────────

@router.post("/generate", summary="提交素材生成任务")
async def generate_materials(req: GenerateRequest, background_tasks: BackgroundTasks):
    """
    提交品牌信息，后台自动执行：
    1. LLM 生成图片提示词
    2. 调用图片生成 API
    3. AI 质检（不合格自动重试，最多 max_retries 次）
    4. 返回最终图片和质检报告

    **返回 task_id，用 GET /api/v1/tasks/{task_id} 轮询结果。**
    """
    task_id = str(uuid.uuid4())

    initial_state = {
        "brand_name": req.brand_name,
        "brand_style": req.brand_style,
        "product_name": req.product_name,
        "product_description": req.product_description,
        "campaign_type": req.campaign_type,
        # 以下字段由工作流节点填充
        "generated_prompt": "",
        "image_urls": [],
        "quality_score": 0.0,
        "quality_feedback": "",
        "retry_count": 0,
        "max_retries": req.max_retries,
        "status": "started",
        "error_message": "",
    }

    _tasks[task_id] = {"status": "queued", "result": None, "error": None}
    background_tasks.add_task(_run_workflow, task_id, initial_state)

    return {
        "task_id": task_id,
        "status": "queued",
        "message": f"任务已提交。请轮询 GET /api/v1/tasks/{task_id} 查看结果。",
    }


@router.get("/tasks/{task_id}", response_model=TaskResponse, summary="查询任务状态")
async def get_task_status(task_id: str):
    """
    查询任务状态：
    - **queued**    : 已排队，等待执行
    - **running**   : 工作流正在执行中
    - **completed** : 完成，result 字段包含图片 URL 和质检评分
    - **failed**    : 失败，error 字段包含原因
    """
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    task = _tasks[task_id]
    return TaskResponse(task_id=task_id, **task)


@router.get("/health", summary="健康检查")
async def health_check():
    """检查服务状态和当前配置"""
    return {
        "status": "ok",
        "llm_model": settings.LLM_MODEL,
        "image_backend": settings.IMAGE_BACKEND,
        "quality_threshold": settings.QUALITY_THRESHOLD,
        "active_tasks": len([t for t in _tasks.values() if t["status"] == "running"]),
    }
