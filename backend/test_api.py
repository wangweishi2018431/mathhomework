#!/usr/bin/env python3
"""直接测试批改接口，不通过 uvicorn"""
import asyncio
import base64
import sys
import os

# 确保导入的是最新代码
sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

from app.services.ai_service import call_vision_with_refinement
from app.schemas import QuestionResult, CorrectionResponse

async def test():
    # 读取测试图片
    test_img_path = sys.argv[1] if len(sys.argv) > 1 else "test_image.png"

    if not os.path.exists(test_img_path):
        print(f"请提供测试图片路径: python test_api.py <图片路径>")
        print(f"或者创建一个 test_image.png 在 backend 目录")
        return

    with open(test_img_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode("utf-8")

    print(f"测试图片: {test_img_path}")
    print(f"图片大小: {len(image_base64)} 字符")
    print("="*60)

    try:
        result = await call_vision_with_refinement(
            image_base64=image_base64,
            mime_type="image/png",
        )

        print("\n>>> AI 原始返回结构:")
        print(f"keys: {result.keys()}")

        print("\n>>> 解析为 Pydantic 模型:")
        questions = result.get("questions", [])
        corrected = []
        for i, q in enumerate(questions):
            print(f"\n题 {i+1} 原始数据:")
            print(f"  q_num: {q.get('q_num')}")
            print(f"  score: {q.get('score')!r} (type: {type(q.get('score')).__name__})")
            print(f"  max_score: {q.get('max_score')!r}")
            print(f"  is_correct: {q.get('is_correct')}")

            qr = QuestionResult(
                q_num=q.get("q_num", i + 1),
                content=q.get("content", ""),
                student_ans=q.get("student_ans", ""),
                is_correct=q.get("is_correct", False),
                score=q.get("score", 0),
                max_score=q.get("max_score", 10),
                analysis=q.get("analysis", ""),
            )
            corrected.append(qr)
            print(f"  -> QuestionResult: score={qr.score}, max_score={qr.max_score}")

        response = CorrectionResponse(questions=corrected)
        print(f"\n>>> 最终响应:")
        print(response.model_dump_json(indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
