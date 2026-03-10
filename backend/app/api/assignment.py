import base64
import logging
import uuid
import asyncio

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, UploadFile, File, Form

from app.config import MAX_IMAGE_SIZE_MB, AI_VISION_API_KEY, AI_TEXT_API_KEY
from app.models.schemas import AssignmentStatus
from app.schemas import (
    AnswerMode,
    AssignmentResponse,
    CorrectedQuestion,
    CreateAssignmentRequest,
    QuestionType,
    StandardAnswer,
    SubmissionResponse,
    TeacherSubmitAnswersRequest,
)
from app.services.ai_service import call_vision, call_vision_with_refinement, call_text, AIServiceError
from app.services.prompts import (
    GENERATE_ANSWER_SYSTEM,
    GENERATE_ANSWER_PROMPT_IMAGE,
    GENERATE_ANSWER_PROMPT_TEXT,
)
from app.services.storage_service import StorageService, get_storage_service
from app.storage import (
    Assignment,
    Submission,
    get_assignment,
    get_submission,
    list_assignments,
    list_submissions_by_assignment,
    save_assignment,
    save_submission,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/assignments", tags=["作业管理"])


@router.post("", response_model=AssignmentResponse, status_code=201)
async def create_assignment(req: CreateAssignmentRequest):
    """教师创建作业项目，提交题目（图片或文字）。"""
    # 校验图片类型题目的 Base64 合法性和大小
    for i, q in enumerate(req.questions):
        if q.type == QuestionType.image:
            try:
                raw = base64.b64decode(q.content)
            except Exception:
                raise HTTPException(status_code=400, detail=f"第 {i + 1} 题的图片 Base64 编码无效")
            if len(raw) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
                raise HTTPException(status_code=400, detail=f"第 {i + 1} 题的图片超过 {MAX_IMAGE_SIZE_MB}MB")

    assignment = Assignment(
        id=uuid.uuid4().hex[:12],
        title=req.title,
        questions=req.questions,
        submit_start_time=req.submit_start_time,
        submit_end_time=req.submit_end_time,
        appeal_end_time=req.appeal_end_time,
        allow_resubmit=req.allow_resubmit,
        allow_late=req.allow_late,
        late_score_rule=req.late_score_rule,
        course_id=req.course_id,
        publish_status="published" if req.submit_start_time else "draft",
    )
    save_assignment(assignment)

    return _to_response(assignment)


@router.get("", response_model=list[AssignmentResponse])
async def get_assignments():
    """获取所有作业项目列表。"""
    return [_to_response(a) for a in list_assignments()]


@router.get("/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment_detail(assignment_id: str):
    """获取单个作业项目详情。"""
    assignment = _get_or_404(assignment_id)
    return _to_response(assignment)


@router.post("/{assignment_id}/answers/ai-generate", response_model=AssignmentResponse)
async def ai_generate_answers(assignment_id: str):
    """选择 AI 自动生成标准答案。"""
    assignment = _get_or_404(assignment_id)

    if assignment.standard_answers:
        raise HTTPException(status_code=409, detail="该作业已存在标准答案，请勿重复生成")

    if not AI_VISION_API_KEY:
        raise HTTPException(status_code=503, detail="AI 服务未配置，请先设置 AI_VISION_API_KEY")

    answers: list[StandardAnswer] = []
    for i, q in enumerate(assignment.questions):
        try:
            if q.type == QuestionType.image:
                result = await call_vision(
                    image_base64=q.content,
                    prompt=GENERATE_ANSWER_PROMPT_IMAGE,
                    system_prompt=GENERATE_ANSWER_SYSTEM,
                )
            else:
                result = await call_text(
                    prompt=GENERATE_ANSWER_PROMPT_TEXT.format(content=q.content),
                    system_prompt=GENERATE_ANSWER_SYSTEM,
                )
            answer_text = result.get("answer", "")
            key_result = result.get("key_result", "")
            full_answer = f"{answer_text}\n\n**最终结果：** {key_result}" if key_result else answer_text
        except AIServiceError as exc:
            logger.warning("第 %d 题 AI 生成失败: %s", i + 1, exc)
            full_answer = f"[AI 生成失败] {exc}"

        answers.append(StandardAnswer(
            question_index=i,
            answer=full_answer,
            source=AnswerMode.ai_generate,
        ))

    assignment.answer_mode = AnswerMode.ai_generate
    assignment.standard_answers = answers
    save_assignment(assignment)

    return _to_response(assignment)


@router.post("/{assignment_id}/answers/teacher-submit", response_model=AssignmentResponse)
async def teacher_submit_answers(assignment_id: str, req: TeacherSubmitAnswersRequest):
    """教师手动提交标准答案。"""
    assignment = _get_or_404(assignment_id)

    if assignment.standard_answers:
        raise HTTPException(status_code=409, detail="该作业已存在标准答案，如需修改请先清除")

    question_count = len(assignment.questions)
    for item in req.answers:
        if item.question_index >= question_count:
            raise HTTPException(
                status_code=400,
                detail=f"题目序号 {item.question_index} 超出范围（共 {question_count} 题，序号从 0 开始）",
            )

    assignment.answer_mode = AnswerMode.teacher_submit
    assignment.standard_answers = [
        StandardAnswer(
            question_index=item.question_index,
            answer=item.answer,
            source=AnswerMode.teacher_submit,
        )
        for item in req.answers
    ]
    save_assignment(assignment)

    return _to_response(assignment)


@router.post("/{assignment_id}/extend", response_model=AssignmentResponse)
async def extend_assignment_deadline(
    assignment_id: str,
    submit_end_time: str = Form(..., description="新的截止时间，ISO 格式如 2026-03-10T23:59:00"),
):
    """延长作业截止时间。"""
    assignment = _get_or_404(assignment_id)
    assignment.submit_end_time = submit_end_time
    save_assignment(assignment)
    return _to_response(assignment)


# ---- 学生提交与批改 ----

@router.post("/{assignment_id}/submit", response_model=SubmissionResponse, status_code=202)
async def student_submit_upload(
    assignment_id: str,
    background_tasks: BackgroundTasks,
    student_name: str = Form(..., description="学生姓名"),
    file: UploadFile = File(...),
    storage: StorageService = Depends(get_storage_service)
):
    """学生提交作业图片（表单上传），触发异步 AI 批改。返回 task_id (submission_id) 供轮询。"""
    assignment = _get_or_404(assignment_id)

    if not assignment.standard_answers:
        raise HTTPException(status_code=409, detail="该作业尚未设置标准答案，无法批改")

    if not AI_VISION_API_KEY:
        raise HTTPException(status_code=503, detail="AI 服务未配置，请先设置 AI_VISION_API_KEY")

    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="仅支持 JPEG / PNG / WebP 格式的图片")

    # 1. 保存图片到 OSS
    image_url = await storage.upload_image(file)

    # 2. 创建 Submission (状态为 processing)
    submission = Submission(
        id=uuid.uuid4().hex[:12],
        assignment_id=assignment_id,
        student_name=student_name,
        image_url=image_url,
        status=AssignmentStatus.processing,
        max_total_score=sum(q.max_score for q in assignment.questions),
    )
    save_submission(submission)

    # 3. 触发异步批改任务
    background_tasks.add_task(
        _process_correction_task,
        submission_id=submission.id,
        assignment=assignment,
        image_url=image_url,
        mime_type=file.content_type,
        storage=storage,
    )

    return _to_submission_response(submission)


@router.get("/{assignment_id}/submissions/{submission_id}", response_model=SubmissionResponse)
async def get_submission_status(assignment_id: str, submission_id: str):
    """前端轮询此接口获取批改状态。"""
    _get_or_404(assignment_id)
    submission = get_submission(submission_id)
    if not submission or submission.assignment_id != assignment_id:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    return _to_submission_response(submission)


@router.get("/{assignment_id}/submissions", response_model=list[SubmissionResponse])
async def get_submissions(assignment_id: str):
    """查看某作业下所有学生提交的批改结果。"""
    _get_or_404(assignment_id)
    submissions = list_submissions_by_assignment(assignment_id)
    return [_to_submission_response(s) for s in submissions]


import traceback

# ---- helpers ----

async def _process_correction_task(
    submission_id: str,
    assignment: Assignment,
    image_url: str,
    mime_type: str,
    storage: StorageService,
):
    """后台任务：调用大模型批改作业并更新状态。"""
    submission = get_submission(submission_id)
    if not submission:
        logger.error(f"批改任务启动失败：未找到 submission_id {submission_id}")
        return

    logger.info(f"开始批改任务 {submission_id}，学生：{submission.student_name}")
    try:
        # 获取图片的 Base64 用于喂给模型
        image_base64 = await storage.get_image_base64(image_url)

        answers_text = _build_answers_text(assignment)

        result = await call_vision_with_refinement(
            image_base64=image_base64,
            standard_answers=answers_text,
            mime_type=mime_type,
        )

        corrected = _parse_correction(result, assignment)

        submission.corrected_questions = corrected
        submission.total_score = sum(q.score for q in corrected)
        submission.status = AssignmentStatus.completed
        logger.info(f"批改任务 {submission_id} 成功完成，得分: {submission.total_score}")

    except AIServiceError as exc:
        logger.error(f"批改任务 {submission_id} AI调用失败: {exc}")
        submission.status = AssignmentStatus.failed
        submission.error_message = f"AI 服务异常: {exc}"
    except Exception as exc:
        logger.error(f"批改任务 {submission_id} 发生未知异常:\n{traceback.format_exc()}")
        submission.status = AssignmentStatus.failed
        submission.error_message = f"系统内部错误: {exc}"
    finally:
        save_submission(submission)


def _to_submission_response(s: Submission) -> SubmissionResponse:
    return SubmissionResponse(
        submission_id=s.id,
        assignment_id=s.assignment_id,
        student_name=s.student_name,
        image_url=s.image_url,
        status=s.status,
        questions=s.corrected_questions,
        total_score=s.total_score,
        max_total_score=s.max_total_score,
        error_message=s.error_message,
        created_at=s.created_at,
    )

def _get_or_404(assignment_id: str) -> Assignment:
    assignment = get_assignment(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="作业项目不存在")
    return assignment


def _to_response(a: Assignment) -> AssignmentResponse:
    # 计算提交进度
    submissions = list_submissions_by_assignment(a.id)
    submitted_count = len(submissions)
    # TODO: 从课程服务获取班级总人数，目前默认30人
    total_students = 30

    return AssignmentResponse(
        id=a.id,
        title=a.title,
        question_count=len(a.questions),
        total_score=sum(q.max_score for q in a.questions),
        questions=a.questions,
        answer_mode=a.answer_mode,
        standard_answers=a.standard_answers,
        created_at=a.created_at,
        submit_start_time=a.submit_start_time,
        submit_end_time=a.submit_end_time,
        appeal_end_time=a.appeal_end_time,
        allow_resubmit=a.allow_resubmit,
        allow_late=a.allow_late,
        late_score_rule=a.late_score_rule,
        publish_status=a.publish_status,
        submitted_count=submitted_count,
        total_students=total_students,
        progress=f"{submitted_count}/{total_students}",
    )


def _build_answers_text(assignment: Assignment) -> str:
    """将标准答案和分值拼成文本，嵌入批改 prompt。"""
    lines: list[str] = []
    answer_map = {sa.question_index: sa.answer for sa in assignment.standard_answers}
    for i, q in enumerate(assignment.questions):
        ans = answer_map.get(i, "（无标准答案）")
        lines.append(f"第 {i + 1} 题（满分 {q.max_score} 分）：\n{ans}")
    return "\n\n".join(lines)


def _parse_correction(result: dict, assignment: Assignment) -> list[CorrectedQuestion]:
    """将 AI 返回的 JSON 解析为 CorrectedQuestion 列表，并校正分值边界。"""
    raw_questions = result.get("questions", [])
    corrected: list[CorrectedQuestion] = []

    # 建立题号 -> 满分的映射（题号从 1 开始）
    max_scores = {i + 1: q.max_score for i, q in enumerate(assignment.questions)}

    for item in raw_questions:
        q_num = item.get("q_num", 0)
        max_score = max_scores.get(q_num, 10.0)
        raw_score = float(item.get("score", 0))
        # 钳制分数在 [0, max_score] 范围内
        score = max(0.0, min(raw_score, max_score))

        corrected.append(CorrectedQuestion(
            q_num=q_num,
            content=item.get("content", ""),
            student_ans=item.get("student_ans", ""),
            is_correct=item.get("is_correct", False),
            max_score=max_score,
            score=score,
            analysis=item.get("analysis", ""),
        ))

    return corrected
