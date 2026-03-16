# 微信云托管 - FastAPI 服务 Dockerfile
# 使用 Python 3.11 轻量级镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装（优先拷贝以利用 Docker 缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 创建上传目录（云托管临时存储）
RUN mkdir -p /app/uploads

# 复制项目源代码
COPY . .

# 暴露端口（微信云托管推荐使用 8080）
EXPOSE 8080

# 启动命令（云托管会通过环境变量注入配置）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
