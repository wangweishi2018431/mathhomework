#!/usr/bin/env python3
"""直接用 Python 运行，不经过 uvicorn"""
import os

import uvicorn

# 禁止缓存
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
SERVER_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("BACKEND_PORT", "18080"))

if __name__ == "__main__":
    print(f"Starting backend at http://{SERVER_HOST}:{SERVER_PORT}")
    uvicorn.run(
        "app.main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=True,
        reload_dirs=["app"],
    )
