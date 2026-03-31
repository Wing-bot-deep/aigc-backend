"""
品牌资产配置表
管理各品牌的 LoRA 模型路径、底座模型、ControlNet 类型、负向提示词等参数。
生产环境可迁移至 PostgreSQL 数据库（见文件末尾建表 SQL 注释）。
"""

# ── 品牌资产主配置 ────────────────────────────────────────────────────────────
BRAND_ASSETS: dict = {
    "维达Tempo": {
        "lora_path": "models/lora/vinda_tempo_v2.safetensors",
        "lora_weight": 0.85,
        "base_model": "flux",           # flux | sdxl
        "controlnet_type": "canny",     # canny（边缘）| depth（深度）
        "style_keywords": "morandi color palette, minimalist luxury, white background",
        "negative_prompt": (
            "deformed product, distorted packaging, logo deformation, text error, "
            "blurry, extra limbs, wrong color, watermark, low quality, nsfw"
        ),
    },
    "汤臣倍健": {
        "lora_path": "models/lora/by_health_v1.safetensors",
        "lora_weight": 0.80,
        "base_model": "sdxl",
        "controlnet_type": "depth",
        "style_keywords": "clean health lifestyle, bright vibrant colors, professional studio",
        "negative_prompt": (
            "deformed capsule, blurry text, wrong product shape, wrong logo, "
            "dark muddy colors, low quality, watermark, nsfw"
        ),
    },
    "利洁时Dettol": {
        "lora_path": "models/lora/dettol_v1.safetensors",
        "lora_weight": 0.80,
        "base_model": "sdxl",
        "controlnet_type": "canny",
        "style_keywords": "clean hygienic, bright green accent, medical professional, studio light",
        "negative_prompt": (
            "dirty, messy, deformed bottle, wrong logo color, blurry, "
            "wrong green shade, low quality, watermark, nsfw"
        ),
    },
    "得宝Tempo": {  # 得宝与维达同系，共享 LoRA
        "lora_path": "models/lora/vinda_tempo_v2.safetensors",
        "lora_weight": 0.85,
        "base_model": "flux",
        "controlnet_type": "canny",
        "style_keywords": "morandi pastel, premium tissue, soft elegant, white background",
        "negative_prompt": (
            "deformed product, logo distortion, text error, blurry packaging, "
            "wrong color palette, low quality, watermark, nsfw"
        ),
    },
    # ── 未配置品牌的兜底默认值 ──────────────────────────────────────────────
    "_default": {
        "lora_path": None,
        "lora_weight": 0.0,
        "base_model": "flux",
        "controlnet_type": "canny",
        "style_keywords": "",
        "negative_prompt": (
            "deformed, blurry, bad anatomy, logo distortion, text error, "
            "watermark, low quality, nsfw, extra objects"
        ),
    },
}


# ── 平台文案风格配置 ──────────────────────────────────────────────────────────
PLATFORM_COPY_STYLE: dict = {
    "小红书": {
        "tone": "种草感强、生活化、第一人称、亲切有共鸣",
        "format": "标题18字以内含emoji，正文150字内分3段，结尾带2~3个话题标签 #xx #xx",
        "key_rules": "开头用场景代入，中间讲体验，结尾引导收藏/评论",
    },
    "抖音": {
        "tone": "节奏快、口播感强、有悬念开头、结尾有明确行动号召(CTA)",
        "format": "标题15字以内，正文100字，开头前3秒制造悬念，结尾 '点击购物车' 或 '戳链接'",
        "key_rules": "每句话不超过15字，多用短句，加数字对比",
    },
    "电商": {
        "tone": "突出核心卖点、强调价值主张、简洁有力、可信度强",
        "format": "主标题（10字内）+ 副标题（20字内）+ 3条卖点（每条15字内）+ 促销利益点",
        "key_rules": "用具体数字，避免形容词堆砌，突出差异化",
    },
}


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def get_brand_config(brand_name: str) -> dict:
    """查找品牌配置，未命中时返回默认配置"""
    return BRAND_ASSETS.get(brand_name, BRAND_ASSETS["_default"])


def list_brands() -> list:
    """返回所有已配置品牌列表"""
    return [k for k in BRAND_ASSETS.keys() if not k.startswith("_")]


# ── 生产环境数据库建表参考（PostgreSQL）──────────────────────────────────────
"""
-- 品牌资产表
CREATE TABLE brand_assets (
    id          SERIAL PRIMARY KEY,
    brand_name  VARCHAR(100) UNIQUE NOT NULL,
    lora_path   VARCHAR(255),
    lora_weight FLOAT DEFAULT 0.8,
    base_model  VARCHAR(20) DEFAULT 'flux',
    controlnet_type VARCHAR(20) DEFAULT 'canny',
    style_keywords  TEXT,
    negative_prompt TEXT,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- 生成任务表
CREATE TABLE generation_tasks (
    task_id     UUID PRIMARY KEY,
    brand_name  VARCHAR(100),
    product_name VARCHAR(200),
    platform    VARCHAR(50),
    status      VARCHAR(50),
    generated_prompt TEXT,
    negative_prompt  TEXT,
    image_urls  JSONB,
    copy_variants JSONB,
    quality_score FLOAT,
    retry_count INT DEFAULT 0,
    created_at  TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- 内容资产库（DAM）
CREATE TABLE content_assets (
    asset_id    UUID PRIMARY KEY,
    task_id     UUID REFERENCES generation_tasks(task_id),
    brand_name  VARCHAR(100),
    platform    VARCHAR(50),
    image_url   TEXT NOT NULL,
    copy_text   TEXT,
    quality_score FLOAT,
    is_approved BOOLEAN DEFAULT FALSE,
    approved_by VARCHAR(100),
    created_at  TIMESTAMP DEFAULT NOW()
);
"""
