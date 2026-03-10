"""课程 & 花名册管理路由 —— 老师手动导入学生。"""

from __future__ import annotations

import io
import csv

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from app.services.roster_service import (
    CourseRoster,
    RosterService,
    StudentInfo,
)

router = APIRouter(prefix="/api/v1/courses", tags=["课程管理"])

# 单例服务
_roster_svc = RosterService()


# ---- 请求体 ----

class CreateCourseRequest(BaseModel):
    course_id: str = Field(..., description="课程编号，如 MATH201")
    course_name: str = Field(..., description="课程名称")


class AddStudentRequest(BaseModel):
    student_id: str = Field(..., description="学号")
    name: str = Field(..., description="姓名")
    class_name: str = Field("", description="班级")


# ---- 课程管理 ----

@router.post("", response_model=CourseRoster, summary="创建课程")
async def create_course(req: CreateCourseRequest):
    return await _roster_svc.create_course(req.course_id, req.course_name)


@router.get("", response_model=list[CourseRoster], summary="列出所有课程")
async def list_courses():
    return await _roster_svc.list_courses()


@router.delete("/{course_id}", summary="删除课程")
async def delete_course(course_id: str):
    deleted = await _roster_svc.delete_course(course_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="课程不存在")
    return {"message": f"课程 {course_id} 已删除"}


# ---- 学生名单 ----

@router.get("/{course_id}/students", response_model=CourseRoster, summary="获取课程学生名单")
async def get_course_students(course_id: str):
    return await _roster_svc.get_students_by_course(course_id)


@router.post("/{course_id}/students", response_model=CourseRoster, summary="添加单个学生")
async def add_student(course_id: str, req: AddStudentRequest):
    try:
        return await _roster_svc.add_student(
            course_id,
            StudentInfo(student_id=req.student_id, name=req.name, class_name=req.class_name),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/{course_id}/students/{student_id}",
    response_model=CourseRoster,
    summary="移除学生",
)
async def remove_student(course_id: str, student_id: str):
    try:
        return await _roster_svc.remove_student(course_id, student_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---- 批量导入（Excel / CSV） ----

@router.post(
    "/{course_id}/students/import",
    response_model=CourseRoster,
    summary="从 Excel/CSV 文件批量导入学生",
)
async def import_students(
    course_id: str,
    file: UploadFile = File(..., description="Excel(.xlsx) 或 CSV 文件"),
):
    """
    文件格式要求（表头）：学号, 姓名, 班级
    - CSV: 直接按逗号分隔
    - Excel: 读取第一个 Sheet
    """
    content = await file.read()
    students: list[StudentInfo] = []

    if file.filename and file.filename.endswith(".xlsx"):
        try:
            import openpyxl
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="服务端未安装 openpyxl，无法解析 Excel 文件",
            )
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            raise HTTPException(status_code=400, detail="文件内容为空")
        # 跳过表头，逐行解析
        for row in rows[1:]:
            if not row or not row[0]:
                continue
            students.append(
                StudentInfo(
                    student_id=str(row[0]).strip(),
                    name=str(row[1]).strip() if row[1] else "",
                    class_name=str(row[2]).strip() if len(row) > 2 and row[2] else "",
                )
            )
    else:
        # 当作 CSV 处理
        text = content.decode("utf-8-sig")  # 兼容 BOM
        reader = csv.reader(io.StringIO(text))
        header = next(reader, None)
        if not header:
            raise HTTPException(status_code=400, detail="文件内容为空")
        for row in reader:
            if not row or not row[0].strip():
                continue
            students.append(
                StudentInfo(
                    student_id=row[0].strip(),
                    name=row[1].strip() if len(row) > 1 else "",
                    class_name=row[2].strip() if len(row) > 2 else "",
                )
            )

    if not students:
        raise HTTPException(status_code=400, detail="未解析到有效的学生数据")

    try:
        roster = await _roster_svc.batch_import_students(course_id, students)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return roster
