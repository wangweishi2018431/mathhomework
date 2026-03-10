from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# ---- 图片批改（已有） ----

class ImageRequest(BaseModel):
    image_base64: str


# ---- 题目识别与解答（教师端） ----

class SolveQuestionRequest(BaseModel):
    """教师指定题目求解请求。"""
    image_base64: str = Field(..., description="题目图片的 Base64 编码")
    specifications: str = Field(
        ...,
        description="题目指定，如：'第3题'、'第一大题第3小题'、'1-3, 5'、'一、3；三、2'"
    )


class SolutionStep(BaseModel):
    """解题步骤。"""
    idea: str = Field(default="", description="解题思路说明")
    steps: list[str] = Field(default_factory=list, description="详细推导步骤")
    answer: str = Field(default="", description="最终答案")


class SolvedQuestion(BaseModel):
    """单道题目的解答结果。"""
    specification: str = Field(..., description="教师的原始指定")
    found: bool = Field(..., description="是否成功找到该题目")
    q_number: str = Field(default="", description="识别到的题号")
    content: str = Field(default="", description="完整的题目内容（LaTeX）")
    question_type: str = Field(default="", description="题目类型")
    knowledge_points: list[str] = Field(default_factory=list, description="相关知识点")
    difficulty: str = Field(default="", description="难度评估")
    solution: SolutionStep = Field(default_factory=SolutionStep, description="结构化解答")
    full_solution: str = Field(default="", description="完整解答文本（LaTeX）")
    error_message: str = Field(default="", description="错误信息（如未找到）")


class SolveSummary(BaseModel):
    """解答汇总信息。"""
    total_specified: int = Field(..., description="指定的题目数量")
    found_count: int = Field(..., description="成功找到的题目数量")
    not_found: list[str] = Field(default_factory=list, description="未找到的指定列表")


class SolveQuestionResponse(BaseModel):
    """题目解答响应。"""
    specified_questions: list[SolvedQuestion] = Field(..., description="各指定题目的解答")
    summary: SolveSummary = Field(..., description="汇总信息")


class QuestionResult(BaseModel):
    q_num: int
    content: str
    student_ans: str
    is_correct: bool
    score: float = Field(default=0.0, description="AI评分")
    max_score: float = Field(default=10.0, description="该题满分")
    analysis: str


class CorrectionResponse(BaseModel):
    questions: list[QuestionResult]


# ---- 作业项目 ----

class QuestionType(str, Enum):
    image = "image"
    text = "text"


class AnswerMode(str, Enum):
    ai_generate = "ai_generate"
    teacher_submit = "teacher_submit"


class QuestionItem(BaseModel):
    """单道题目：可以是图片（Base64）或纯文字。"""
    type: QuestionType
    content: str = Field(..., description="题目内容：type=text 时为文字，type=image 时为 Base64 编码的图片")
    max_score: float = Field(default=10.0, ge=0, description="该题满分分值，默认 10 分")


class CreateAssignmentRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="作业标题")
    questions: list[QuestionItem] = Field(..., min_length=1, description="题目列表（至少一道）")

    # 新增：时间配置
    submit_start_time: str | None = Field(default=None, description="提交开始时间，ISO 格式如 2026-03-06T10:00:00")
    submit_end_time: str | None = Field(default=None, description="提交截止时间，ISO 格式")
    appeal_end_time: str | None = Field(default=None, description="申诉截止时间，ISO 格式")

    # 新增：规则配置
    allow_resubmit: bool = Field(default=True, description="是否允许订正重交")
    allow_late: bool = Field(default=True, description="是否允许逾期提交")
    late_score_rule: str = Field(default="100%", description="逾期计分规则：100%/80%/60%/0%")

    # 新增：关联课程
    course_id: str | None = Field(default=None, description="关联课程ID")


class TeacherAnswerItem(BaseModel):
    """教师为某道题目提供的标准答案。"""
    question_index: int = Field(..., ge=0, description="题目序号（从 0 开始）")
    answer: str = Field(..., min_length=1, description="标准答案内容（支持 LaTeX）")


class TeacherSubmitAnswersRequest(BaseModel):
    answers: list[TeacherAnswerItem] = Field(..., min_length=1)


class StandardAnswer(BaseModel):
    question_index: int
    answer: str
    source: AnswerMode


class AssignmentResponse(BaseModel):
    id: str
    title: str
    question_count: int
    total_score: float
    questions: list[QuestionItem]
    answer_mode: AnswerMode | None = None
    standard_answers: list[StandardAnswer] = []
    created_at: str

    # 新增：时间配置
    submit_start_time: str | None = None
    submit_end_time: str | None = None
    appeal_end_time: str | None = None

    # 新增：规则配置
    allow_resubmit: bool = True
    allow_late: bool = True
    late_score_rule: str = "100%"

    # 新增：发布状态和进度
    publish_status: str = "draft"
    submitted_count: int = 0  # 已提交人数
    total_students: int = 0   # 班级总人数
    progress: str = "0/0"     # 进度显示如 "3/30"


from app.models.schemas import AssignmentStatus

# ---- 学生提交与批改 ----

class StudentSubmitRequest(BaseModel):
    """学生提交作业（拍照上传）。"""
    student_name: str = Field(..., min_length=1, max_length=100, description="学生姓名")
    image_base64: str = Field(..., description="作业图片的 Base64 编码")
    mime_type: str = Field(default="image/png", description="图片 MIME 类型")


class CorrectedQuestion(BaseModel):
    """单题批改结果。"""
    q_num: int = Field(..., description="题号（从 1 开始）")
    content: str = Field(default="", description="识别出的题目内容")
    student_ans: str = Field(default="", description="学生的解答过程")
    is_correct: bool = Field(..., description="是否完全正确")
    max_score: float = Field(..., description="该题满分")
    score: float = Field(..., description="AI 评分")
    analysis: str = Field(default="", description="批改分析（含 LaTeX）")


class SubmissionResponse(BaseModel):
    """批改结果响应。"""
    submission_id: str
    assignment_id: str
    student_name: str
    image_url: str
    status: AssignmentStatus
    questions: list[CorrectedQuestion]
    total_score: float = Field(default=0.0, description="总得分")
    max_total_score: float = Field(default=0.0, description="满分总分")
    error_message: str | None = None
    created_at: str
