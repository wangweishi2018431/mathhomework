"""封装大模型 Vision API 调用（兼容 OpenAI Chat Completions 格式）。"""

from __future__ import annotations

import json
import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# 大模型 API 调用超时（秒），Vision 请求通常较慢
_TIMEOUT = httpx.Timeout(connect=10, read=120, write=10, pool=10)


async def call_vision(
    *,
    image_base64: str,
    prompt: str,
    system_prompt: str = "",
    mime_type: str = "image/png",
) -> dict:
    """发送图片 + 文字给大模型 Vision API，返回解析后的 JSON dict。

    Args:
        image_base64: 图片的 Base64 编码（不含 data:image/... 前缀）。
        prompt: 用户侧文字提示。
        system_prompt: 系统提示词。
        mime_type: 图片 MIME 类型，默认 image/png。

    Returns:
        大模型返回内容解析后的 dict。

    Raises:
        AIServiceError: 调用或解析失败时抛出。
    """
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{image_base64}",
                },
            },
            {"type": "text", "text": prompt},
        ],
    })

    return await _chat_completion(
        messages,
        api_key=settings.AI_VISION_API_KEY,
        api_base_url=settings.AI_VISION_API_BASE_URL,
        model_name=settings.AI_VISION_MODEL_NAME,
    )


async def call_text(
    *,
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.1,
) -> dict:
    """纯文字请求大模型（格式修正专用），返回解析后的 JSON dict。"""
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    return await _chat_completion(
        messages,
        api_key=settings.AI_TEXT_API_KEY,
        api_base_url=settings.AI_TEXT_API_BASE_URL,
        model_name=settings.AI_TEXT_MODEL_NAME,
        temperature=temperature,
    )


# ---- internal ----

async def _chat_completion(
    messages: list[dict],
    api_key: str,
    api_base_url: str,
    model_name: str,
    temperature: float = 0.2,
    return_raw: bool = False,
) -> dict | str:
    """调用 OpenAI 兼容的 /chat/completions 接口。

    Args:
        return_raw: 如果为 True，返回原始文本字符串；否则解析 JSON 并返回 dict。
    """
    url = f"{api_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: dict = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
    }
    if not return_raw:
        payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("AI API HTTP error %s: %s", exc.response.status_code, exc.response.text)
            raise AIServiceError(f"AI 服务返回错误: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error("AI API request failed: %s", exc)
            raise AIServiceError("无法连接 AI 服务") from exc

    body = resp.json()
    raw_content = body["choices"][0]["message"]["content"]

    if return_raw:
        return raw_content

    # JSON 模式：解析并修正评分
    logger.debug("AI raw response preview: %s", raw_content[:1500])

    data = _parse_json(raw_content)
    data = _force_step_scoring(data)

    logger.debug("Corrected scores: %s", [
        f"题{q.get('q_num')}: {q.get('score')}/{q.get('max_score')}"
        for q in data.get("questions", [])
    ])

    return data


def _force_step_scoring(data: dict) -> dict:
    """强制修正不合理的评分。

    如果学生写了内容但 AI 给了 0 分，给默认步骤分。
    """
    questions = data.get("questions", [])
    for q in questions:
        score = q.get("score", 0)
        max_score = q.get("max_score", 10)
        student_ans = q.get("student_ans", "")
        analysis = q.get("analysis", "")

        # 如果写了内容但给了 0 分
        if score == 0 and student_ans and student_ans != "未作答":
            # 检查是否提到方法正确、公式正确等
            if any(kw in analysis for kw in ["方法正确", "公式正确", "思路正确", "使用", "用了"]):
                # 给 50%-70% 的步骤分
                q["score"] = int(max_score * 0.6)
                q["analysis"] = f"{analysis}\n\n【系统修正】AI 原判 0 分不合理，已调整为步骤分 {q['score']} 分。"
                logger.warning(f"强制修正分数: q_num={q.get('q_num')}, 0分 -> {q['score']}分")

    return data


def _clean_json_text(text: str) -> str:
    """清洗 AI 返回的 JSON 文本，移除 Markdown 标记等杂质。"""
    text = text.strip()

    # 1. 移除开头的 ```json 或 ``` 标记（支持多种变体）
    # 匹配 ```json 或 ``` 开头，可能带有换行
    text = re.sub(r'^```(?:json|JSON)?\s*\n?', '', text)
    # 移除结尾的 ``` 标记
    text = re.sub(r'\n?```\s*$', '', text)

    # 2. 移除可能的零宽字符
    text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')

    # 3. 处理常见的 LaTeX 转义问题
    # 修复单层反斜杠（如果不是已转义的双反斜杠）
    # 这是一个启发式修复，将 \int 转为 \\int
    # 但要注意不要破坏已经是 \\ 的
    # 使用负向前瞻/后顾来避免重复转义

    return text.strip()


def _fix_latex_escapes(text: str) -> str:
    """修复 LaTeX 公式中的反斜杠转义问题。

    将单条反斜杠转换为双反斜杠，但避免重复转义。
    例如：\\int -> \\\\int，但 \\\\int 保持不变。
    """
    result = []
    i = 0
    while i < len(text):
        if text[i] == '\\':
            # 检查后面是否已经有另一个反斜杠（已经是转义过的）
            if i + 1 < len(text) and text[i + 1] == '\\':
                # 已经是双反斜杠，保持不变
                result.append('\\\\')
                i += 2
            else:
                # 单条反斜杠，需要转义为双反斜杠
                result.append('\\\\')
                i += 1
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)


def _parse_json(text: str) -> dict:
    """从大模型返回的文本中提取并解析 JSON。

    处理流程：
    1. 清洗文本（移除 Markdown 代码块标记等）
    2. 尝试直接解析
    3. 如果失败，尝试修复常见的 JSON 格式问题
    4. 返回解析后的 dict 或抛出详细错误
    """
    original_text = text
    text = _clean_json_text(text)

    # 尝试 1: 直接解析清洗后的文本
    try:
        data = json.loads(text)
        return _ensure_latex_wrapped(data)
    except json.JSONDecodeError as e:
        logger.debug(f"第一次 JSON 解析失败: {e}")

    # 尝试 2: 修复 LaTeX 转义问题
    # 将单条反斜杠转换为双反斜杠（但要避免重复转义）
    try:
        fixed_text = _fix_latex_escapes(text)
        data = json.loads(fixed_text)
        return _ensure_latex_wrapped(data)
    except json.JSONDecodeError as e:
        logger.debug(f"修复转义后解析仍失败: {e}")

    # 尝试 3: 查找文本中第一个 { 到最后一个 } 的内容
    # 有些 AI 会在 JSON 前后添加解释性文字
    try:
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            json_text = text[start_idx:end_idx + 1]
            # 对提取的片段也做 LaTeX 转义修复
            json_text = _fix_latex_escapes(json_text)
            data = json.loads(json_text)
            return _ensure_latex_wrapped(data)
    except json.JSONDecodeError as e:
        logger.debug(f"提取 JSON 片段后解析仍失败: {e}")

    # 尝试 4: 最后手段 - 尝试用更宽松的方式提取 JSON
    # 寻找 "questions" 字段所在的对象
    try:
        questions_match = re.search(r'"questions"\s*:\s*\[', text)
        if questions_match:
            # 找到 questions 数组的开始，往前找 {
            start_idx = text.rfind('{', 0, questions_match.start())
            if start_idx != -1:
                # 找到匹配的 }
                brace_count = 0
                end_idx = start_idx
                for i in range(start_idx, len(text)):
                    if text[i] == '{':
                        brace_count += 1
                    elif text[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i
                            break
                json_text = text[start_idx:end_idx + 1]
                json_text = _fix_latex_escapes(json_text)
                data = json.loads(json_text)
                return _ensure_latex_wrapped(data)
    except Exception as e:
        logger.debug(f"宽松提取后解析仍失败: {e}")

    # 所有尝试都失败，记录详细错误并抛出
    logger.error(f"JSON 解析失败。原始文本前 800 字符: {original_text[:800]}")
    logger.error(f"清洗后文本前 800 字符: {text[:800]}")

    # 尝试定位具体的错误位置
    try:
        json.loads(text)
    except json.JSONDecodeError as e:
        error_msg = str(e)
        # 提取错误位置附近的上下文
        lineno = getattr(e, 'lineno', 0)
        colno = getattr(e, 'colno', 0)
        # 获取错误位置附近的文本
        lines = text.split('\n')
        error_context = ""
        if 0 <= lineno - 1 < len(lines):
            error_line = lines[lineno - 1]
            start = max(0, colno - 30)
            end = min(len(error_line), colno + 30)
            error_context = f"  错误附近: ...{error_line[start:end]}..."
        raise AIServiceError(
            f"JSON 解析失败: {error_msg}。"
            f"错误位置大约在第 {lineno} 行第 {colno} 列。{error_context}"
            f"请检查 AI 返回的 LaTeX 公式是否正确转义（应使用 \\\\int 而非 \\int）"
        ) from e

    raise AIServiceError("无法从 AI 返回内容中解析 JSON，未知错误")


def _ensure_latex_wrapped(data: dict) -> dict:
    """确保所有包含 LaTeX 命令的字符串字段都被 $...$ 包裹。

    AI 经常不遵循指令，只在 analysis 字段用 $ 包裹公式，
    而 content 和 student_ans 字段忘记包裹。此函数自动修复。
    """
    latex_commands = [
        r'\\int', r'\\sum', r'\\prod', r'\\frac', r'\\sqrt', r'\\lim',
        r'\\alpha', r'\\beta', r'\\gamma', r'\\delta', r'\\theta',
        r'\\left', r'\\right', r'\\begin', r'\\end', r'\\infty',
        r'\\pi', r'\\sigma', r'\\omega', r'\\cdot', r'\\times',
        r'\\leq', r'\\geq', r'\\neq', r'\\approx'
    ]
    # 匹配未被 $ 包裹的 LaTeX 命令
    latex_pattern = re.compile(
        r'(?<!\$)(' + '|'.join(latex_commands) + r')(?![^\$]*\$)'
    )

    def wrap_latex(text: str) -> str:
        if not text or not isinstance(text, str):
            return text
        # 如果已经以 $ 开头和结尾，说明已包裹，不处理
        text = text.strip()
        if text.startswith('$') and text.endswith('$'):
            return text
        # 如果包含 $，说明可能已正确包裹，不处理
        if '$' in text:
            return text
        # 检查是否包含 LaTeX 命令
        if not latex_pattern.search(text):
            return text
        # 简化处理：如果文本以 LaTeX 命令开头（前面可能有描述性文字），尝试拆分
        # 查找第一个 LaTeX 命令的位置
        match = latex_pattern.search(text)
        if match:
            # 如果 LaTeX 前面有中文或描述文字，只包裹公式部分
            prefix = text[:match.start()].strip()
            formula = text[match.start():].strip()
            # 清理公式末尾的多余字符
            formula = re.sub(r'[,:;，：；\s]+$', '', formula)
            if prefix:
                return f"{prefix}${formula}$"
            else:
                return f"${formula}$"
        return f'${text}$'

    def process_dict(obj):
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                # 只处理特定字段
                if k in ('content', 'student_ans', 'answer', 'key_result'):
                    result[k] = wrap_latex(v) if isinstance(v, str) else v
                elif isinstance(v, dict):
                    result[k] = process_dict(v)
                elif isinstance(v, list):
                    result[k] = process_list(v)
                else:
                    result[k] = v
            return result
        return obj

    def process_list(obj):
        if isinstance(obj, list):
            return [process_dict(item) if isinstance(item, dict) else item for item in obj]
        return obj

    return process_dict(data)


# ---- 两步流程：视觉 OCR 提取 + 纯文本数学批改 ----

from app.services.prompts import (
    STEP1_OCR_SYSTEM, STEP1_OCR_PROMPT, STEP2_GRADE_SYSTEM, STEP2_GRADE_PROMPT,
    SOLVE_QUESTION_SYSTEM, SOLVE_QUESTION_PROMPT_TEMPLATE,
)


async def _chat_completion_text(
    messages: list[dict],
    api_key: str,
    api_base_url: str,
    model_name: str,
    temperature: float = 0.2,
) -> str:
    """调用大模型，返回原始文本（不解析 JSON）。"""
    url = f"{api_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # 第一步不需要强制 JSON 输出
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("AI API HTTP error %s: %s", exc.response.status_code, exc.response.text)
            raise AIServiceError(f"AI 服务返回错误: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error("AI API request failed: %s", exc)
            raise AIServiceError("无法连接 AI 服务") from exc

    body = resp.json()
    return body["choices"][0]["message"]["content"]


async def call_ocr_extract(
    *,
    image_base64: str,
    mime_type: str = "image/png",
) -> str:
    """第一步：视觉模型纯 OCR 提取题目和学生解答。"""
    messages: list[dict] = []
    messages.append({"role": "system", "content": STEP1_OCR_SYSTEM})
    messages.append({
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
            },
            {"type": "text", "text": STEP1_OCR_PROMPT},
        ],
    })

    return await _chat_completion_text(
        messages,
        api_key=settings.AI_VISION_API_KEY,
        api_base_url=settings.AI_VISION_API_BASE_URL,
        model_name=settings.AI_VISION_MODEL_NAME,
        temperature=0.1,
    )


async def call_grade_text(
    *,
    extracted_text: str,
    standard_answers: str = "",
) -> dict:
    """第二步：纯文本模型数学验算 + 批改，输出 JSON。"""
    prompt = STEP2_GRADE_PROMPT.format(
        extracted_text=extracted_text,
        standard_answers=standard_answers or "无标准答案，请自行验算",
    )

    messages: list[dict] = []
    messages.append({"role": "system", "content": STEP2_GRADE_SYSTEM})
    messages.append({"role": "user", "content": prompt})

    raw_content = await _chat_completion(
        messages,
        api_key=settings.AI_TEXT_API_KEY,
        api_base_url=settings.AI_TEXT_API_BASE_URL,
        model_name=settings.AI_TEXT_MODEL_NAME,
        temperature=0.1,
    )

    return raw_content


async def call_vision_with_refinement(
    *,
    image_base64: str,
    standard_answers: str = "",
    mime_type: str = "image/png",
) -> dict:
    """两步流程：视觉 OCR 提取 → 纯文本数学批改。

    第一步：视觉模型提取题目和学生解答为 LaTeX 文本（不做批改）
    第二步：纯文本模型数学验算、批改、评分，输出 JSON
    """
    # 第一步：OCR 提取
    print(f"\n{'='*60}")
    print("开始两步流程: 视觉OCR -> 纯文本批改")
    print(f"{'='*60}\n")
    print(f">>> 第一步: 视觉模型 OCR 提取...")
    print(f"使用模型: {settings.AI_VISION_MODEL_NAME}")
    extracted_text = await call_ocr_extract(
        image_base64=image_base64,
        mime_type=mime_type,
    )
    print(f">>> OCR 提取完成, 长度: {len(extracted_text)} 字符")

    # 第二步：数学批改
    print(f">>> 第二步: 纯文本模型数学批改...")
    print(f"使用模型: {settings.AI_TEXT_MODEL_NAME}")
    result = await call_grade_text(
        extracted_text=extracted_text,
        standard_answers=standard_answers,
    )

    # 打印第二步返回的分数
    import sys
    print(f">>> 批改完成!")
    for q in result.get("questions", []):
        score = q.get("score")
        max_score = q.get("max_score")
        print(f"  题{q.get('q_num')}: score={score!r} (type={type(score).__name__}), max_score={max_score!r}")
        print(f"  分析: {q.get('analysis', '')[:80]}...")
    print(f"\n{'='*60}\n")

    # 确保每个问题都有 score 和 max_score
    for q in result.get("questions", []):
        if q.get("score") is None:
            # AI 没给分，根据 is_correct 给默认分
            if q.get("is_correct"):
                q["score"] = q.get("max_score", 10)
            else:
                q["score"] = 0
            print(f"[警告] 题{q.get('q_num')} 缺少score，已默认设置为 {q['score']}")
        if q.get("max_score") is None:
            q["max_score"] = 10
            print(f"[警告] 题{q.get('q_num')} 缺少max_score，已默认设置为 10")

    # 把 OCR 提取的原始内容也返回，方便调试
    result['_ocr_extracted'] = extracted_text
    return result


async def call_solve_questions(
    *,
    image_base64: str,
    specifications: str,
    mime_type: str = "image/png",
) -> dict:
    """题目识别与解答：根据教师指定，识别题目并给出完整解答。

    Args:
        image_base64: 题目图片的 Base64 编码。
        specifications: 教师的题目指定（如"第一大题第3小题"）。
        mime_type: 图片 MIME 类型。

    Returns:
        包含各题目解答的 dict。
    """
    prompt = SOLVE_QUESTION_PROMPT_TEMPLATE.format(specifications=specifications)

    messages: list[dict] = [
        {"role": "system", "content": SOLVE_QUESTION_SYSTEM},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
                },
                {"type": "text", "text": prompt},
            ],
        },
    ]

    # 判断是否使用独立的题目求解模型（如 Gemini/Claude）
    use_solve_model = settings.SOLVE_API_KEY and settings.SOLVE_API_BASE_URL and settings.SOLVE_MODEL_NAME

    if use_solve_model:
        print(f"\n{'='*60}")
        print("开始题目识别与解答 [使用独立强模型]")
        print(f"模型: {settings.SOLVE_MODEL_NAME}")
        print(f"指定: {specifications}")
        print(f"{'='*60}\n")

        result = await _chat_completion(
            messages,
            api_key=settings.SOLVE_API_KEY,
            api_base_url=settings.SOLVE_API_BASE_URL,
            model_name=settings.SOLVE_MODEL_NAME,
            temperature=0.2,
        )
    else:
        print(f"\n{'='*60}")
        print("开始题目识别与解答 [使用视觉模型]")
        print(f"指定: {specifications}")
        print(f"{'='*60}\n")

        result = await _chat_completion(
            messages,
            api_key=settings.AI_VISION_API_KEY,
            api_base_url=settings.AI_VISION_API_BASE_URL,
            model_name=settings.AI_VISION_MODEL_NAME,
            temperature=0.2,
        )

    print(f">>> 解答完成!")
    summary = result.get("summary", {})
    print(f"  指定: {summary.get('total_specified', 0)} 题")
    print(f"  找到: {summary.get('found_count', 0)} 题")
    print(f"\n{'='*60}\n")

    return result


class AIServiceError(Exception):
    """AI 服务调用异常。"""
