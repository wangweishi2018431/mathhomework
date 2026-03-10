"""对象存储 (OSS) 抽象服务。

未来切换微信云存储或阿里 OSS 时，新建子类并在 get_storage_service() 注入。
"""

from __future__ import annotations

import os
import uuid
import logging
from abc import ABC, abstractmethod
from fastapi import UploadFile

logger = logging.getLogger(__name__)

# 本地模拟 OSS 的存储目录
LOCAL_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)


class StorageService(ABC):
    @abstractmethod
    async def upload_image(self, file: UploadFile) -> str:
        """上传图片，返回公网可访问的 URL（或用于拉取的对象键）。"""
        ...

    @abstractmethod
    async def get_image_base64(self, image_url: str) -> str:
        """根据 URL/键 获取图片的 Base64 编码（喂给大模型）。"""
        ...


class LocalStorageMock(StorageService):
    """本地文件系统模拟 OSS（开发调试用）。"""

    async def upload_image(self, file: UploadFile) -> str:
        ext = file.filename.split(".")[-1] if "." in file.filename else "png"
        new_filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(LOCAL_UPLOAD_DIR, new_filename)

        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)

        # 实际应返回类似 http://oss.example.com/...
        # 这里返回一个伪协议以便标识
        url = f"local-oss://{new_filename}"
        logger.info(f"图片保存至本地模拟 OSS: {filepath}")
        return url

    async def get_image_base64(self, image_url: str) -> str:
        import base64

        if not image_url.startswith("local-oss://"):
            raise ValueError(f"无法识别的模拟 URL: {image_url}")

        filename = image_url.replace("local-oss://", "")
        filepath = os.path.join(LOCAL_UPLOAD_DIR, filename)

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"模拟 OSS 中未找到图片: {filename}")

        with open(filepath, "rb") as f:
            content = f.read()

        return base64.b64encode(content).decode("utf-8")


# ---- 依赖注入 ----
def get_storage_service() -> StorageService:
    return LocalStorageMock()
