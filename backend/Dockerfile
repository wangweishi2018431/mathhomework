# 使用官方 Python 3.10 轻量级镜像作为基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 安装系统依赖（如需后续安装 postgresql 等驱动可在此补充）
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装依赖
# 优先拷贝 requirements 以利用 Docker 缓存层
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 创建预留的上传目录（供 LocalStorageMock 使用，尽管云端应挂载或用真实 OSS）
RUN mkdir -p /uploads

# 复制项目源代码
COPY . .

# 暴露端口（微信云托管默认会将流量路由到容器的 80 端口，可通过 container.config.json 修改）
EXPOSE 80

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]
