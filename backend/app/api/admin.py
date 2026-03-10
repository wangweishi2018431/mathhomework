"""管理员 API - 配置热重载管理。"""

import httpx
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class AdminLoginRequest(BaseModel):
    """管理员登录请求。"""
    password: str = Field(..., min_length=1, description="管理员密码")


class AdminLoginResponse(BaseModel):
    """管理员登录响应。"""
    success: bool
    token: str = Field(default="", description="简单令牌（预留扩展）")


class ConfigResponse(BaseModel):
    """配置信息响应（隐藏敏感信息）。"""
    AI_VISION_API_BASE_URL: str
    AI_VISION_MODEL_NAME: str
    AI_TEXT_API_BASE_URL: str
    AI_TEXT_MODEL_NAME: str
    SOLVE_API_BASE_URL: str
    SOLVE_MODEL_NAME: str
    MAX_IMAGE_SIZE_MB: int


class ConfigUpdateRequest(BaseModel):
    """配置更新请求。"""
    password: str = Field(..., min_length=1, description="管理员密码")
    AI_VISION_API_KEY: str | None = Field(default=None, description="视觉模型 API Key")
    AI_VISION_API_BASE_URL: str | None = Field(default=None, description="视觉模型 Base URL")
    AI_TEXT_API_KEY: str | None = Field(default=None, description="文本模型 API Key")
    AI_TEXT_API_BASE_URL: str | None = Field(default=None, description="文本模型 Base URL")
    AI_TEXT_MODEL_NAME: str | None = Field(default=None, description="文本模型名称")
    SOLVE_API_KEY: str | None = Field(default=None, description="题目求解模型 API Key")
    SOLVE_API_BASE_URL: str | None = Field(default=None, description="题目求解模型 Base URL")
    SOLVE_MODEL_NAME: str | None = Field(default=None, description="题目求解模型名称")


class ConfigUpdateResponse(BaseModel):
    """配置更新响应。"""
    success: bool
    message: str
    config: ConfigResponse


def _verify_admin(password: str | None):
    """验证管理员密码。"""
    if not password:
        raise HTTPException(status_code=401, detail="缺少管理员密码")
    if not settings.verify_admin(password):
        raise HTTPException(status_code=401, detail="密码错误")


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(req: AdminLoginRequest):
    """管理员登录验证。"""
    if settings.verify_admin(req.password):
        return AdminLoginResponse(success=True, token="admin")
    raise HTTPException(status_code=401, detail="密码错误")


@router.get("/config", response_model=ConfigResponse)
async def get_config(x_admin_password: str = Header(..., description="管理员密码")):
    """获取当前配置（隐藏敏感信息如 API Key）。"""
    _verify_admin(x_admin_password)
    return ConfigResponse(**settings.get_public_config())


@router.post("/config", response_model=ConfigUpdateResponse)
async def update_config(req: ConfigUpdateRequest):
    """热更新配置。

    更新内存中的配置并写入 .env 文件，立即生效。
    """
    _verify_admin(req.password)

    # 收集需要更新的字段
    updates = {}
    if req.AI_VISION_API_KEY is not None:
        updates["AI_VISION_API_KEY"] = req.AI_VISION_API_KEY
    if req.AI_VISION_API_BASE_URL is not None:
        updates["AI_VISION_API_BASE_URL"] = req.AI_VISION_API_BASE_URL
    if req.AI_TEXT_API_KEY is not None:
        updates["AI_TEXT_API_KEY"] = req.AI_TEXT_API_KEY
    if req.AI_TEXT_API_BASE_URL is not None:
        updates["AI_TEXT_API_BASE_URL"] = req.AI_TEXT_API_BASE_URL
    if req.AI_TEXT_MODEL_NAME is not None:
        updates["AI_TEXT_MODEL_NAME"] = req.AI_TEXT_MODEL_NAME
    if req.SOLVE_API_KEY is not None:
        updates["SOLVE_API_KEY"] = req.SOLVE_API_KEY
    if req.SOLVE_API_BASE_URL is not None:
        updates["SOLVE_API_BASE_URL"] = req.SOLVE_API_BASE_URL
    if req.SOLVE_MODEL_NAME is not None:
        updates["SOLVE_MODEL_NAME"] = req.SOLVE_MODEL_NAME

    if not updates:
        raise HTTPException(status_code=400, detail="没有提供要更新的配置")

    try:
        # 热更新：更新内存 + 写入文件
        settings.update_config(**updates)

        return ConfigUpdateResponse(
            success=True,
            message="配置已更新并立即生效",
            config=ConfigResponse(**settings.get_public_config())
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"配置更新失败: {exc}")


class ModelListRequest(BaseModel):
    """模型列表查询请求。"""
    api_key: str = Field(..., description="API Key")
    base_url: str = Field(..., description="Base URL")


class ModelInfo(BaseModel):
    """模型信息。"""
    id: str
    name: str
    description: str = ""


class ModelListResponse(BaseModel):
    """模型列表响应。"""
    success: bool
    models: list[ModelInfo]
    provider: str = ""  # 服务商名称
    message: str = ""


# 硬编码的常用模型列表（用于不支持列表 API 的服务商）
COMMON_MODELS = {
    "qwen": [
        ModelInfo(id="qwen-vl-max", name="通义千问 VL Max", description="阿里云最强视觉模型"),
        ModelInfo(id="qwen-vl-plus", name="通义千问 VL Plus", description="阿里云视觉模型"),
        ModelInfo(id="qwen-max", name="通义千问 Max", description="阿里云最强文本模型"),
        ModelInfo(id="qwen-plus", name="通义千问 Plus", description="阿里云文本模型"),
        ModelInfo(id="qwen-turbo", name="通义千问 Turbo", description="阿里云快速文本模型"),
    ],
    "claude": [
        ModelInfo(id="claude-3-7-sonnet-20250219", name="Claude 3.7 Sonnet", description="Anthropic 最新智能模型"),
        ModelInfo(id="claude-3-5-sonnet-20241022", name="Claude 3.5 Sonnet", description="Anthropic 高性价比模型"),
        ModelInfo(id="claude-3-5-haiku-20241022", name="Claude 3.5 Haiku", description="Anthropic 快速模型"),
        ModelInfo(id="claude-3-opus-20240229", name="Claude 3 Opus", description="Anthropic 最强模型"),
    ],
    "gemini": [
        ModelInfo(id="gemini-2.5-pro-exp-03-25", name="Gemini 2.5 Pro", description="Google 实验性最强模型"),
        ModelInfo(id="gemini-2.0-flash", name="Gemini 2.0 Flash", description="Google 快速多模态模型"),
        ModelInfo(id="gemini-2.0-flash-lite", name="Gemini 2.0 Flash Lite", description="Google 轻量快速模型"),
        ModelInfo(id="gemini-1.5-pro", name="Gemini 1.5 Pro", description="Google 专业模型"),
        ModelInfo(id="gemini-1.5-flash", name="Gemini 1.5 Flash", description="Google 快速模型"),
    ],
    "openai": [
        ModelInfo(id="gpt-4o", name="GPT-4o", description="OpenAI 最强多模态模型"),
        ModelInfo(id="gpt-4o-mini", name="GPT-4o Mini", description="OpenAI 高性价比模型"),
        ModelInfo(id="gpt-4-turbo", name="GPT-4 Turbo", description="OpenAI 文本模型"),
        ModelInfo(id="gpt-3.5-turbo", name="GPT-3.5 Turbo", description="OpenAI 快速模型"),
    ],
    "deepseek": [
        ModelInfo(id="deepseek-chat", name="DeepSeek Chat", description="DeepSeek 对话模型"),
        ModelInfo(id="deepseek-reasoner", name="DeepSeek Reasoner", description="DeepSeek 推理模型"),
    ],
}


def _detect_provider(base_url: str) -> str:
    """根据 base_url 检测服务商类型。"""
    base_lower = base_url.lower()

    if "dashscope" in base_lower or "aliyun" in base_lower:
        return "qwen"
    elif "anthropic" in base_lower:
        return "claude"
    elif "google" in base_lower or "generativelanguage" in base_lower:
        return "gemini"
    elif "deepseek" in base_lower:
        return "deepseek"
    elif "openai" in base_lower or "api.openai.com" in base_lower:
        return "openai"
    else:
        return "unknown"


async def _fetch_openai_compatible_models(api_key: str, base_url: str) -> list[ModelInfo]:
    """获取 OpenAI 兼容格式的模型列表。"""
    url = f"{base_url.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    models = []
    for item in data.get("data", []):
        model_id = item.get("id", "")
        # 过滤出常用模型（排除 embeddings、tts 等非聊天模型）
        if any(keyword in model_id.lower() for keyword in [
            "gpt", "claude", "gemini", "qwen", "deepseek",
            "turbo", "vision", "vl", "chat", "pro", "flash"
        ]):
            models.append(ModelInfo(
                id=model_id,
                name=model_id,
                description=""
            ))

    return models


@router.post("/models", response_model=ModelListResponse)
async def get_model_list(
    req: ModelListRequest,
    x_admin_password: str = Header(..., description="管理员密码")
):
    """获取指定 API Key 可用的模型列表。

    根据 Base URL 自动识别服务商类型：
    - OpenAI 兼容格式：直接调用 /v1/models
    - 通义千问/Claude/DeepSeek：返回硬编码常用模型列表
    """
    _verify_admin(x_admin_password)

    if not req.api_key or not req.base_url:
        return ModelListResponse(
            success=False,
            models=[],
            message="API Key 和 Base URL 不能为空"
        )

    provider = _detect_provider(req.base_url)

    # 对于已知但不支持列表 API 的服务商，返回硬编码列表
    if provider in COMMON_MODELS:
        return ModelListResponse(
            success=True,
            models=COMMON_MODELS[provider],
            provider=provider,
            message=f"已加载 {provider} 常用模型列表"
        )

    # 尝试 OpenAI 兼容格式获取
    try:
        models = await _fetch_openai_compatible_models(req.api_key, req.base_url)

        if models:
            return ModelListResponse(
                success=True,
                models=models,
                provider="openai_compatible",
                message=f"成功获取 {len(models)} 个模型"
            )
        else:
            # 如果没有获取到模型，返回 OpenAI 常用模型作为备选
            return ModelListResponse(
                success=True,
                models=COMMON_MODELS["openai"],
                provider="unknown",
                message="未获取到模型列表，显示 OpenAI 常用模型供参考"
            )

    except httpx.HTTPStatusError as exc:
        # API 调用失败，可能是 Key 无效或服务商不支持
        return ModelListResponse(
            success=False,
            models=COMMON_MODELS.get("openai", []),
            provider=provider,
            message=f"获取模型列表失败 ({exc.response.status_code})，请检查 API Key 是否有效"
        )
    except Exception as exc:
        return ModelListResponse(
            success=False,
            models=COMMON_MODELS.get("openai", []),
            provider=provider,
            message=f"获取模型列表失败: {str(exc)[:100]}"
        )


@router.get("/config/test")
async def test_ai_connection(
    x_admin_password: str = Header(..., description="管理员密码")
):
    """测试 AI 配置是否可用。"""
    _verify_admin(x_admin_password)

    results = {
        "vision": {"configured": False, "message": ""},
        "text": {"configured": False, "message": ""},
        "solve": {"configured": False, "message": ""},
    }

    # 检查视觉模型配置
    if settings.AI_VISION_API_KEY and settings.AI_VISION_API_BASE_URL:
        results["vision"]["configured"] = True
        results["vision"]["message"] = f"已配置模型: {settings.AI_VISION_MODEL_NAME}"
    else:
        results["vision"]["message"] = "API Key 或 Base URL 未配置"

    # 检查文本模型配置
    if settings.AI_TEXT_API_KEY and settings.AI_TEXT_API_BASE_URL:
        results["text"]["configured"] = True
        results["text"]["message"] = f"已配置模型: {settings.AI_TEXT_MODEL_NAME}"
    else:
        results["text"]["message"] = "API Key 或 Base URL 未配置"

    # 检查题目求解模型配置
    if settings.SOLVE_API_KEY and settings.SOLVE_API_BASE_URL:
        results["solve"]["configured"] = True
        results["solve"]["message"] = f"已配置模型: {settings.SOLVE_MODEL_NAME}"
    else:
        results["solve"]["message"] = "未配置（将使用视觉模型作为备选）"

    return {
        "configured": results["vision"]["configured"] or results["text"]["configured"],
        "details": results,
        "note": "此检查仅验证配置是否填写，不验证 API Key 是否有效"
    }
