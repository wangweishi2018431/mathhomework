"""MVP 阶段的内存存储，后续替换为数据库。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.models.schemas import AssignmentStatus
from app.schemas import AnswerMode, CorrectedQuestion, QuestionItem, StandardAnswer

@dataclass
class Assignment:
    id: str
    title: str
    questions: list[QuestionItem]
    answer_mode: AnswerMode | None = None
    standard_answers: list[StandardAnswer] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 新增：时间配置
    submit_start_time: str | None = field(default=None)
    submit_end_time: str | None = field(default=None)
    appeal_end_time: str | None = field(default=None)

    # 新增：规则配置
    allow_resubmit: bool = field(default=True)
    allow_late: bool = field(default=True)
    late_score_rule: str = field(default="100%")

    # 新增：关联课程和状态
    course_id: str | None = field(default=None)
    publish_status: str = field(default="draft")  # draft/published/closed


@dataclass
class Submission:
    id: str
    assignment_id: str
    student_name: str
    image_url: str = field(default="")
    status: AssignmentStatus = field(default=AssignmentStatus.pending)
    corrected_questions: list[CorrectedQuestion] = field(default_factory=list)
    total_score: float = field(default=0.0)
    max_total_score: float = field(default=0.0)
    error_message: str | None = field(default=None)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 新增：提交状态和时间
    submit_status: str = field(default="submitted")  # not_submitted/submitted/graded/appealed
    submit_time: str = field(default_factory=lambda: datetime.now().isoformat())
    is_late: bool = field(default=False)
    resubmit_count: int = field(default=0)


# 简单的内存字典
_assignments: dict[str, Assignment] = {}
_submissions: dict[str, Submission] = {}


def save_assignment(assignment: Assignment) -> None:
    _assignments[assignment.id] = assignment


def get_assignment(assignment_id: str) -> Assignment | None:
    return _assignments.get(assignment_id)


def list_assignments() -> list[Assignment]:
    return list(_assignments.values())


def save_submission(submission: Submission) -> None:
    _submissions[submission.id] = submission


def get_submission(submission_id: str) -> Submission | None:
    return _submissions.get(submission_id)


def list_submissions_by_assignment(assignment_id: str) -> list[Submission]:
    return [s for s in _submissions.values() if s.assignment_id == assignment_id]
