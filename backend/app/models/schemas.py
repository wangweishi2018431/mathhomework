"""完善的数据库 Schema 设计（Pydantic 模型，未来可映射到 SQLAlchemy/Tortoise ORM）。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# ---- 枚举类型 ----

class AssignmentStatus(str, Enum):
    """作业批改状态机"""
    pending = "pending"          # 等待处理
    processing = "processing"    # 正在调用 AI 批改中
    completed = "completed"      # 批改完成
    failed = "failed"            # 批改失败


class QuestionType(str, Enum):
    """题目类型"""
    image = "image"
    text = "text"


# ---- 核心实体 ----

class User(BaseModel):
    """用户表（老师/学生）"""
    id: str = Field(..., description="内部用户 ID")
    wx_openid: str | None = Field(default=None, description="微信 OpenID")
    name: str = Field(..., max_length=100, description="姓名")
    student_id: str | None = Field(default=None, description="学号（学生专属）")
    role: str = Field(default="student", description="角色：student / teacher")
    created_at: datetime = Field(default_factory=datetime.now)


class Question(BaseModel):
    """单题表"""
    id: str = Field(..., description="题目 ID")
    assignment_id: str = Field(..., description="所属作业项目 ID")
    q_num: int = Field(..., description="题号")
    type: QuestionType = Field(default=QuestionType.image)
    content: str = Field(..., description="题目内容（文字或图片 URL）")
    max_score: float = Field(default=10.0, ge=0, description="满分")
    knowledge_tags: list[str] = Field(default_factory=list, description="知识点标签（如：微积分、矩阵求逆等）")
    standard_answer: str | None = Field(default=None, description="标准答案（LaTeX）")
    created_at: datetime = Field(default_factory=datetime.now)


class AssignmentPublishStatus(str, Enum):
    """作业发布状态"""
    draft = "draft"         # 草稿
    published = "published" # 已发布
    closed = "closed"       # 已结束


class AssignmentDef(BaseModel):
    """作业项目定义表（老师创建的模版）"""
    id: str = Field(..., description="作业项目 ID")
    teacher_id: str = Field(..., description="创建教师 ID")
    title: str = Field(..., max_length=200, description="作业标题")
    course_id: str | None = Field(default=None, description="关联课程 ID（如 MATH201）")

    # 时间配置
    submit_start_time: datetime | None = Field(default=None, description="提交开始时间")
    submit_end_time: datetime | None = Field(default=None, description="提交截止时间")
    appeal_end_time: datetime | None = Field(default=None, description="申诉截止时间")

    # 规则配置
    allow_resubmit: bool = Field(default=True, description="是否允许订正重交")
    allow_late: bool = Field(default=True, description="是否允许逾期提交")
    late_score_rule: str = Field(default="100%", description="逾期计分规则：100%/80%/60%/0%")

    # 状态
    publish_status: AssignmentPublishStatus = Field(default=AssignmentPublishStatus.draft, description="发布状态")

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class SubmitStatus(str, Enum):
    """学生提交状态"""
    not_submitted = "not_submitted"  # 未提交
    submitted = "submitted"          # 已提交
    graded = "graded"                # 已批改
    appealed = "appealed"            # 已申诉


class Submission(BaseModel):
    """学生提交记录表（作业实例）"""
    id: str = Field(..., description="提交记录 ID (同时可作为 task_id)")
    assignment_id: str = Field(..., description="所属作业项目 ID")
    student_id: str = Field(..., description="提交学生 ID")
    image_url: str = Field(..., description="学生上传的作业图片 OSS 地址")

    # 状态
    status: AssignmentStatus = Field(default=AssignmentStatus.pending, description="批改状态")
    submit_status: SubmitStatus = Field(default=SubmitStatus.submitted, description="提交状态")

    # 提交信息
    submit_time: datetime = Field(default_factory=datetime.now, description="实际提交时间")
    is_late: bool = Field(default=False, description="是否逾期提交")
    resubmit_count: int = Field(default=0, description="订正重交次数")

    total_score: float | None = Field(default=None, description="总得分（批改完成后填充）")
    error_message: str | None = Field(default=None, description="失败时的错误信息")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class CorrectedQuestionRecord(BaseModel):
    """单题批改结果表"""
    id: str = Field(..., description="记录 ID")
    submission_id: str = Field(..., description="所属提交记录 ID")
    question_id: str = Field(..., description="对应的原题目 ID")
    student_ans: str = Field(default="", description="学生解答内容")
    is_correct: bool = Field(default=False, description="是否完全正确")
    score: float = Field(default=0.0, description="得分")
    analysis: str = Field(default="", description="批改分析")
    created_at: datetime = Field(default_factory=datetime.now)
