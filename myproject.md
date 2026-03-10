# 项目名称：AI 数学作业批改微信小程序 (类似“数你最灵”)

## 1. 项目概述
本项目是一个基于大模型视觉能力（Vision）的微信小程序，主要用于自动批改中小学/高校数学作业。
核心能力包括：拍照/选图上传 -> AI 识别题目、解答与正误判断 -> 返回带 LaTeX 公式的详细解析 -> 前端渲染展示。

## 2. 技术栈选型
*   **架构模式**：前后端分离。前端极轻量，核心逻辑与 AI API 调用全部在 Python 后端。
*   **前端（微信小程序端）**：
    *   原生 WXML/WXSS/JS
    *   UI 框架：Vant Weapp 或 TDesign
    *   公式渲染：引入 `Towxml` 或 `mp-html` 解析大模型返回的 LaTeX 数学公式。
*   **后端（Python端）**：
    *   框架：FastAPI (异步框架，适合长时间的 AI API 等待)
    *   部署环境：微信云托管 (Weixin Cloud Run) - 容器化 Docker 部署，免域名和备案。
*   **AI 大模型**：
    *   前期测试接入国内多模态大模型（如 Qwen-VL 或 GLM-4V），要求输出严格的 JSON 格式。

## 3. 核心业务工作流 (MVP 第一阶段目标)
1.  **用户端**：小程序点击“拍照批改” -> 选图/裁剪 -> 压缩图片 -> 调用后端接口。
2.  **后端处理**：FastAPI 接收图片 (Base64) -> 组装 System Prompt -> 异步调用大模型 Vision API。
3.  **AI 预期输出格式 (JSON)**：
    ```json
    {
      "questions":[
        {
          "q_num": 1,
          "content": "识别出的题目内容与公式",
          "student_ans": "学生的解答过程",
          "is_correct": false,
          "analysis": "错误原因及正确解法（包含 LaTeX 公式）"
        }
      ]
    }
    ```
4.  **结果展示**：前端接收 JSON，利用富文本插件渲染排版，展示批改卡片。

## 4. 后续规划（暂时不在 MVP 中实现，但代码需留出扩展性）
*   “一键申诉”人工复核机制。
*   基于数据库（MySQL/PostgreSQL）的错题本与学情图谱。
*   携带错题上下文的“AI 专属助教”追问功能。

## 5. 当前任务（已同步到 2026-03-06）
- [x] FastAPI 后端基础结构完成
- [x] 图片上传接口与 Base64 接口完成（`/api/v1/correct/upload`、`/api/v1/correct/base64`）
- [x] 前后端本地联调打通（微信小程序上传 -> 后端批改 -> 结果展示）
- [x] 作业/提交/课程/学生导入等核心流程 API 完成
- [x] AI 返回 JSON 容错与 LaTeX 转义修复完成
- [x] 本地开发端口统一迁移到 `18080`
- [x] 新增 `start_backend.ps1` / `stop_backend.ps1`，解决 Ctrl+C 未完全退出导致的服务残留问题
- [x] 公式渲染组件集成（`mp-html` 或 `Towxml`）
- [x] 学生端登录能力（`wx.getUserProfile`）
- [x] 教师端页面（创建作业、管理花名册）
- [x] 前端源码编码统一为 UTF-8 无 BOM（修复 `app.json` 解析错误）
- [ ] 下一步：微信云托管部署  ← 当前下一步

## 6. 本地启动约定（当前）
在 `D:/myproject/backend` 目录：

```bash
# 推荐：先清理端口残留再启动
.\start_backend.ps1

# 手动兜底：强制停止残留进程
.\stop_backend.ps1 -Port 18080
```

前端默认请求地址：`http://127.0.0.1:18080`



