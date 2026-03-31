"""
LangGraph 工作流组装
完整流向：
  START
    └─► lora_selector      (查找品牌 LoRA / 底座模型配置)
            └─► prompt_generator  (LLM 生成图片提示词)
            └─► copywriting       (LLM 生成文案，与 prompt_generator 并行)
                    └─► image_generator   (调用图片生成 API)
                            └─► quality_checker  (AI 质检 + 递增 retry_count)
                                    ├─► [score 达标 或 重试超限] ─► result_packager ─► END
                                    └─► [score 不达标] ──────────► prompt_generator (循环优化)
"""
from langgraph.graph import StateGraph, END, START

from .state import MarketingState
from .nodes import (
    lora_selector_node,
    prompt_generator_node,
    copywriting_node,
    image_generator_node,
    quality_checker_node,
    result_packager_node,
    should_continue,
)


def build_workflow():
    graph = StateGraph(MarketingState)

    # ── 注册节点 ──────────────────────────────────────────────────────────────
    graph.add_node("lora_selector", lora_selector_node)
    graph.add_node("prompt_generator", prompt_generator_node)
    graph.add_node("copywriting", copywriting_node)
    graph.add_node("image_generator", image_generator_node)
    graph.add_node("quality_checker", quality_checker_node)
    graph.add_node("result_packager", result_packager_node)

    # ── 定义边 ────────────────────────────────────────────────────────────────
    graph.add_edge(START, "lora_selector")
    graph.add_edge("lora_selector", "prompt_generator")
    graph.add_edge("lora_selector", "copywriting")      # 并行：文案与提示词同时生成
    graph.add_edge("prompt_generator", "image_generator")
    graph.add_edge("copywriting", "image_generator")    # 两个并行节点都完成后才进入生图

    graph.add_edge("image_generator", "quality_checker")

    # ── 条件边（质检后路由）──────────────────────────────────────────────────
    graph.add_conditional_edges(
        "quality_checker",
        should_continue,
        {
            "complete": "result_packager",   # 质量达标或达到重试上限
            "retry": "prompt_generator",     # 质量不达标，带反馈重新生成
        },
    )

    graph.add_edge("result_packager", END)

    return graph.compile()


# 全局单例，供 FastAPI 路由调用
workflow = build_workflow()
