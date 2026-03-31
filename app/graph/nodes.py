"""
LangGraph 节点定义
完整工作流：
  lora_selector → prompt_generator + copywriting (并行) → image_generator → quality_checker → result_packager
"""
import json
import re
import uuid
import httpx
from typing import List

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from .state import MarketingState
from ..config import settings
from ..brand_assets import get_brand_config, PLATFORM_COPY_STYLE


# ── LLM 单例 ──────────────────────────────────────────────────────────────────
def _get_llm():
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        max_tokens=2048,
    )


# ── 节点 1：LoRA 选择器（从品牌资产配置填充 state）────────────────────────────
def lora_selector_node(state: MarketingState) -> dict:
    """根据品牌名称查找对应的 LoRA / 底座模型配置，写入 state。"""
    brand_cfg = get_brand_config(state["brand_name"])
    return {
        "lora_path": brand_cfg.get("lora_path") or "",
        "lora_weight": brand_cfg.get("lora_weight", 0.0),
        "base_model": brand_cfg.get("base_model", "flux"),
        "controlnet_type": brand_cfg.get("controlnet_type", "canny"),
        "negative_prompt": brand_cfg.get("negative_prompt", ""),
        "status": "lora_selected",
    }


# ── 节点 2：Prompt 生成器 ────────────────────────────────────────────────────
def prompt_generator_node(state: MarketingState) -> dict:
    """
    调用 LLM，将用户简短关键词扩写为：
    - 英文正向图片提示词（generated_prompt）
    如果有质检反馈（quality_feedback），则基于反馈迭代优化提示词。
    """
    llm = _get_llm()

    brand_cfg = get_brand_config(state["brand_name"])
    style_keywords = brand_cfg.get("style_keywords", "")
    feedback_section = ""
    if state.get("quality_feedback"):
        feedback_section = f"""
上一版图片的质检反馈如下，请根据反馈优化提示词：
{state['quality_feedback']}
"""

    system_prompt = """你是一位专业的 AI 图片提示词工程师，擅长为商业营销素材生成高质量的 Stable Diffusion / Flux 提示词。
你的提示词必须：
1. 全部使用英文
2. 确保商品包装不形变（在提示词中强调 product integrity、exact packaging）
3. 符合品牌视觉风格
4. 输出格式：只输出一行英文提示词，不要任何解释或其他内容"""

    user_message = f"""请为以下营销素材生成图片提示词：

品牌：{state['brand_name']}
品牌视觉风格关键词：{state.get('brand_style', style_keywords)}
商品：{state['product_name']}
商品描述：{state['product_description']}
投放场景/卖点：{state['campaign_type']}
投放平台：{state.get('platform', '小红书')}
{feedback_section}

要求：输出高质量英文 Stable Diffusion 提示词，强调 exact product packaging integrity, no logo distortion。"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ])

    generated_prompt = response.content.strip()
    return {
        "generated_prompt": generated_prompt,
        "status": "prompt_generated",
    }


# ── 节点 3：文案生成器 ────────────────────────────────────────────────────────
def copywriting_node(state: MarketingState) -> dict:
    """
    基于品牌信息 + 平台风格，生成 3 套带 Emoji 的营销文案。
    """
    llm = _get_llm()
    platform = state.get("platform", "小红书")
    platform_cfg = PLATFORM_COPY_STYLE.get(platform, PLATFORM_COPY_STYLE["小红书"])

    system_prompt = f"""你是一位顶级的{platform}营销文案专家，擅长撰写高转化率的种草文案。
平台风格要求：
- 语调：{platform_cfg['tone']}
- 格式：{platform_cfg['format']}
- 关键规则：{platform_cfg['key_rules']}"""

    user_message = f"""请为以下商品生成 3 套不同风格的{platform}营销文案：

品牌：{state['brand_name']}
商品：{state['product_name']}
商品描述：{state['product_description']}
核心卖点/场景：{state['campaign_type']}

输出格式（严格按此 JSON 格式）：
{{
  "variants": [
    "第一套完整文案（标题+正文）",
    "第二套完整文案（标题+正文）",
    "第三套完整文案（标题+正文）"
  ]
}}"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ])

    try:
        # 提取 JSON
        raw = response.content.strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            copy_variants = data.get("variants", [])
        else:
            copy_variants = [raw]
    except (json.JSONDecodeError, AttributeError):
        copy_variants = [response.content.strip()]

    return {
        "copy_variants": copy_variants,
        "status": "copywriting_done",
    }


# ── 节点 4：图片生成器 ────────────────────────────────────────────────────────
def image_generator_node(state: MarketingState) -> dict:
    """
    根据 IMAGE_BACKEND 配置路由到不同的生图后端：
    - mock    : 返回占位图 URL（本地开发用）
    - dalle3  : 调用 OpenAI DALL-E 3
    - comfyui : 调用本地 ComfyUI（含 LoRA + ControlNet）
    """
    backend = settings.IMAGE_BACKEND

    if backend == "mock":
        image_urls = _mock_generate(state)
    elif backend == "dalle3":
        image_urls = _dalle3_generate(state)
    elif backend == "comfyui":
        image_urls = _comfyui_generate(state)
    else:
        raise ValueError(f"未知的 IMAGE_BACKEND: {backend}")

    return {
        "image_urls": image_urls,
        "status": "image_generated",
    }


def _mock_generate(state: MarketingState) -> List[str]:
    """开发/测试用 mock，返回 picsum 占位图。"""
    seed = abs(hash(state["generated_prompt"])) % 1000
    return [
        f"https://picsum.photos/seed/{seed}/1024/1024",
        f"https://picsum.photos/seed/{seed + 1}/1024/1024",
    ]


def _dalle3_generate(state: MarketingState) -> List[str]:
    """调用 OpenAI DALL-E 3 API 生成图片。"""
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # DALL-E 3 每次只能生成 1 张
    response = client.images.generate(
        model="dall-e-3",
        prompt=state["generated_prompt"],
        size="1024x1024",
        quality="hd",
        n=1,
    )
    return [response.data[0].url]


def _comfyui_generate(state: MarketingState) -> List[str]:
    """
    调用本地 ComfyUI API，动态组装：
    Base Model (Flux/SDXL) + LoRA + ControlNet → 生图 → 轮询结果
    """
    comfyui_url = settings.COMFYUI_URL

    # 动态构建 ComfyUI workflow payload
    prompt_payload = _build_comfyui_workflow(state)

    # 提交任务
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(f"{comfyui_url}/prompt", json={"prompt": prompt_payload})
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]

    # 轮询等待完成（最多 120 秒）
    import time
    for _ in range(60):
        time.sleep(2)
        with httpx.Client(timeout=10.0) as client:
            history_resp = client.get(f"{comfyui_url}/history/{prompt_id}")
            history = history_resp.json()

        if prompt_id in history:
            outputs = history[prompt_id].get("outputs", {})
            image_urls = []
            for node_output in outputs.values():
                for img in node_output.get("images", []):
                    filename = img["filename"]
                    subfolder = img.get("subfolder", "")
                    url = f"{comfyui_url}/view?filename={filename}&subfolder={subfolder}&type=output"
                    image_urls.append(url)
            return image_urls if image_urls else [f"{comfyui_url}/view?filename=error.png"]

    raise TimeoutError(f"ComfyUI 生图超时，prompt_id={prompt_id}")


def _build_comfyui_workflow(state: MarketingState) -> dict:
    """
    动态组装 ComfyUI API workflow：
    CheckpointLoader → LoRA (可选) → ControlNet (可选) → KSampler → 保存
    """
    # 底座模型映射
    model_map = {
        "flux": "flux1-dev-fp8.safetensors",
        "sdxl": "sd_xl_base_1.0.safetensors",
    }
    checkpoint_name = model_map.get(state.get("base_model", "flux"), "flux1-dev-fp8.safetensors")

    workflow: dict = {
        # 1. 加载底座模型
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint_name},
        },
        # 2. 正向提示词
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": state["generated_prompt"],
                "clip": ["1", 1],
            },
        },
        # 3. 负向提示词
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": state.get("negative_prompt", "low quality, blurry, deformed"),
                "clip": ["1", 1],
            },
        },
        # 4. 空 Latent 图像
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 1024, "height": 1024, "batch_size": 2},
        },
        # 5. KSampler
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": int(uuid.uuid4().int % (2**32)),
                "steps": 28,
                "cfg": 7.0,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
            },
        },
        # 6. VAE 解码
        "6": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
        },
        # 7. 保存图片
        "7": {
            "class_type": "SaveImage",
            "inputs": {"images": ["6", 0], "filename_prefix": "aigc_marketing"},
        },
    }

    # 动态插入 LoRA（如果有配置）
    lora_path = state.get("lora_path", "")
    if lora_path:
        workflow["lora"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["1", 0],
                "clip": ["1", 1],
                "lora_name": lora_path,
                "strength_model": state.get("lora_weight", 0.8),
                "strength_clip": state.get("lora_weight", 0.8),
            },
        }
        # 将 KSampler 的 model 输入改为 LoRA 输出
        workflow["5"]["inputs"]["model"] = ["lora", 0]
        workflow["2"]["inputs"]["clip"] = ["lora", 1]
        workflow["3"]["inputs"]["clip"] = ["lora", 1]

    # 动态插入 ControlNet（如果有参考图）
    ref_image_url = state.get("product_ref_image_url", "")
    if ref_image_url:
        controlnet_map = {
            "canny": "control_v11p_sd15_canny.pth",
            "depth": "control_v11f1p_sd15_depth.pth",
        }
        controlnet_name = controlnet_map.get(state.get("controlnet_type", "canny"), "control_v11p_sd15_canny.pth")

        workflow["cn_loader"] = {
            "class_type": "ControlNetLoader",
            "inputs": {"control_net_name": controlnet_name},
        }
        workflow["cn_image"] = {
            "class_type": "LoadImageFromURL",
            "inputs": {"url": ref_image_url},
        }
        workflow["cn_apply"] = {
            "class_type": "ControlNetApply",
            "inputs": {
                "conditioning": ["2", 0],
                "control_net": ["cn_loader", 0],
                "image": ["cn_image", 0],
                "strength": 0.9,
            },
        }
        # 将 KSampler positive 改为 ControlNet 输出
        workflow["5"]["inputs"]["positive"] = ["cn_apply", 0]

    return workflow


# ── 节点 5：质检器 ────────────────────────────────────────────────────────────
def quality_checker_node(state: MarketingState) -> dict:
    """
    使用 LLM-as-Judge 对生成图片进行质检：
    - 评分 0~10
    - 给出具体的改进反馈（供 prompt_generator 重试时使用）
    - 递增 retry_count
    """
    llm = _get_llm()

    image_urls = state.get("image_urls", [])
    if not image_urls:
        return {
            "quality_score": 0.0,
            "quality_feedback": "图片生成失败，未返回任何图片URL",
            "retry_count": state.get("retry_count", 0) + 1,
            "status": "quality_failed",
        }

    system_prompt = """你是一位专业的营销素材质检专家，负责评估 AI 生成的商业营销图片质量。
评估维度：
1. 商品包装完整性（Logo/文字是否形变，权重 40%）
2. 品牌视觉风格契合度（色调、风格，权重 30%）
3. 画面美观度和商业可用性（构图、光影，权重 30%）

输出格式（严格按此 JSON 格式）：
{
  "score": 评分数字(0-10),
  "feedback": "具体问题描述和改进建议（如果分数低于7分必须详细说明）"
}"""

    # 构建包含图片 URL 的评估请求
    image_desc = "\n".join([f"图片{i+1}: {url}" for i, url in enumerate(image_urls[:2])])
    user_message = f"""请对以下 AI 生成的营销素材进行质检：

品牌：{state['brand_name']}
商品：{state['product_name']}
使用的提示词：{state.get('generated_prompt', '')}

生成的图片：
{image_desc}

注意：如果是 mock URL（picsum.photos），请给出 7.5 分的模拟评分，反馈为"mock模式，跳过真实质检"。
请按 JSON 格式输出评分和反馈。"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ])

    try:
        raw = response.content.strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            score = float(data.get("score", 5.0))
            feedback = data.get("feedback", "")
        else:
            score = 5.0
            feedback = raw
    except (json.JSONDecodeError, ValueError):
        score = 5.0
        feedback = response.content.strip()

    return {
        "quality_score": score,
        "quality_feedback": feedback,
        "retry_count": state.get("retry_count", 0) + 1,
        "status": "quality_checked",
    }


# ── 节点 6：结果打包器 ────────────────────────────────────────────────────────
def result_packager_node(state: MarketingState) -> dict:
    """
    将最终生成结果整理打包，写入最终状态。
    生产环境可在此处将结果写入 PostgreSQL / DAM 内容资产库。
    """
    return {
        "status": "completed",
        "error_message": "",
    }


# ── 条件路由函数 ──────────────────────────────────────────────────────────────
def should_continue(state: MarketingState) -> str:
    """
    质检后的路由判断：
    - quality_score >= QUALITY_THRESHOLD 或 retry_count >= max_retries → "complete"
    - 否则 → "retry"（回到 prompt_generator 重新生成）
    """
    score = state.get("quality_score", 0.0)
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)

    if score >= settings.QUALITY_THRESHOLD or retry_count >= max_retries:
        return "complete"
    return "retry"
