import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置管理。
    优先从环境变量读取，本地调试时可从 .env 读取。
    微信云托管的容器会自动注入配置在控制台的环境变量。
    """

    # AI 视觉模型配置（第一步 - 图片识别）
    AI_VISION_API_KEY: str = ""
    AI_VISION_API_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    AI_VISION_MODEL_NAME: str = "qwen-vl-max"

    # AI 纯文本模型配置（第二步 - 格式修正）
    AI_TEXT_API_KEY: str = ""
    AI_TEXT_API_BASE_URL: str = "https://api.openai.com/v1"
    AI_TEXT_MODEL_NAME: str = "gpt-4o-mini"

    # 教师端题目求解专用配置（单步强模型，如 Gemini/Claude）
    SOLVE_API_KEY: str = ""
    SOLVE_API_BASE_URL: str = ""
    SOLVE_MODEL_NAME: str = ""

    # 上传与业务限制
    MAX_IMAGE_SIZE_MB: int = 5

    # 预留给后续数据库与 OSS 扩展的配置
    DATABASE_URL: str = "sqlite:///./test.db"
    OSS_ACCESS_KEY: str = ""
    OSS_SECRET_KEY: str = ""
    OSS_BUCKET_NAME: str = ""
    OSS_ENDPOINT: str = ""

    # 管理员密码（简单验证）
    ADMIN_PASSWORD: str = "admin123"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # 忽略多余的环境变量
    )

    def update_config(self, **kwargs):
        """热更新配置：更新内存并写入.env文件。"""
        env_file_path = self.model_config.get('env_file', '.env')

        # 读取现有.env内容
        env_vars = {}
        if os.path.exists(env_file_path):
            with open(env_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()

        # 更新传入的配置
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                env_vars[key] = value

        # 写回.env文件
        with open(env_file_path, 'w', encoding='utf-8') as f:
            f.write("# AI 数学作业批改服务配置\n")
            f.write("# 此文件由管理员端自动管理\n\n")

            f.write("# AI 视觉模型配置\n")
            f.write(f"AI_VISION_API_KEY={env_vars.get('AI_VISION_API_KEY', '')}\n")
            f.write(f"AI_VISION_API_BASE_URL={env_vars.get('AI_VISION_API_BASE_URL', '')}\n")
            f.write(f"AI_VISION_MODEL_NAME={env_vars.get('AI_VISION_MODEL_NAME', '')}\n\n")

            f.write("# AI 纯文本模型配置\n")
            f.write(f"AI_TEXT_API_KEY={env_vars.get('AI_TEXT_API_KEY', '')}\n")
            f.write(f"AI_TEXT_API_BASE_URL={env_vars.get('AI_TEXT_API_BASE_URL', '')}\n")
            f.write(f"AI_TEXT_MODEL_NAME={env_vars.get('AI_TEXT_MODEL_NAME', '')}\n\n")

            f.write("# 教师端题目求解专用配置（单步强模型）\n")
            f.write(f"SOLVE_API_KEY={env_vars.get('SOLVE_API_KEY', '')}\n")
            f.write(f"SOLVE_API_BASE_URL={env_vars.get('SOLVE_API_BASE_URL', '')}\n")
            f.write(f"SOLVE_MODEL_NAME={env_vars.get('SOLVE_MODEL_NAME', '')}\n\n")

            f.write("# 业务限制\n")
            f.write(f"MAX_IMAGE_SIZE_MB={env_vars.get('MAX_IMAGE_SIZE_MB', '5')}\n\n")

            f.write("# 管理员配置\n")
            f.write(f"ADMIN_PASSWORD={env_vars.get('ADMIN_PASSWORD', 'admin123')}\n\n")

            f.write("# 数据库和存储（预留）\n")
            f.write(f"DATABASE_URL={env_vars.get('DATABASE_URL', 'sqlite:///./test.db')}\n")

        return True

    def get_public_config(self):
        """获取可公开的配置（隐藏敏感信息）。"""
        return {
            "AI_VISION_API_BASE_URL": self.AI_VISION_API_BASE_URL,
            "AI_VISION_MODEL_NAME": self.AI_VISION_MODEL_NAME,
            "AI_TEXT_API_BASE_URL": self.AI_TEXT_API_BASE_URL,
            "AI_TEXT_MODEL_NAME": self.AI_TEXT_MODEL_NAME,
            "SOLVE_API_BASE_URL": self.SOLVE_API_BASE_URL,
            "SOLVE_MODEL_NAME": self.SOLVE_MODEL_NAME,
            "MAX_IMAGE_SIZE_MB": self.MAX_IMAGE_SIZE_MB,
        }

    def verify_admin(self, password: str) -> bool:
        """验证管理员密码。"""
        return password == self.ADMIN_PASSWORD


# 实例化单例供全局导入
settings = Settings()

# 为兼容旧代码，提供单独导出（推荐直接 import settings）
# 视觉模型配置
AI_VISION_API_KEY = settings.AI_VISION_API_KEY
AI_VISION_API_BASE_URL = settings.AI_VISION_API_BASE_URL
AI_VISION_MODEL_NAME = settings.AI_VISION_MODEL_NAME

# 纯文本模型配置
AI_TEXT_API_KEY = settings.AI_TEXT_API_KEY
AI_TEXT_API_BASE_URL = settings.AI_TEXT_API_BASE_URL
AI_TEXT_MODEL_NAME = settings.AI_TEXT_MODEL_NAME

MAX_IMAGE_SIZE_MB = settings.MAX_IMAGE_SIZE_MB
