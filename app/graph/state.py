from typing import TypedDict, List


class MarketingState(TypedDict):
    # ── 用户输入字段 ──────────────────────────────────────────────────────────
    brand_name: str              # 品牌名称，如 "维达Tempo"
    brand_style: str             # 品牌视觉风格，如 "莫兰迪色，白底轻奢"
    product_name: str            # 产品名称，如 "维达抽纸200抽"
    product_description: str     # 产品描述
    campaign_type: str           # 卖点/场景关键词，如 "轻奢、白领、下午茶场景"
    platform: str                # 投放平台：小红书 / 抖音 / 电商
    product_ref_image_url: str   # 商品白底参考图 URL（ControlNet 防形变使用）

    # ── 品牌资产字段（由 lora_selector 节点从 brand_assets 配置中填充）────────
    lora_path: str               # LoRA 模型文件路径（空字符串表示不挂载）
    lora_weight: float           # LoRA 挂载权重（0.0~1.0）
    base_model: str              # 底座模型：flux / sdxl
    controlnet_type: str         # ControlNet 类型：canny（边缘）/ depth（深度）
    negative_prompt: str         # 负向提示词（来自品牌资产配置）

    # ── 生成过程字段 ──────────────────────────────────────────────────────────
    generated_prompt: str        # LLM 生成的正向图片提示词（英文）
    copy_variants: List[str]     # 文案列表（3套，含Emoji，由 copywriting 节点生成）
    image_urls: List[str]        # 生成图片的 URL 列表
    quality_score: float         # AI 质检评分（0-10）
    quality_feedback: str        # 质检反馈详情（重试时传给提示词节点用于优化）

    # ── 控制字段 ──────────────────────────────────────────────────────────────
    retry_count: int             # 当前重试次数（由质检节点递增）
    max_retries: int             # 最大重试次数（默认 2）
    status: str                  # 当前节点状态，便于调试追踪
    error_message: str           # 错误信息
