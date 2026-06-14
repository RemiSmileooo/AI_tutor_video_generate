"""LLM 模块：把原始文案拆解为结构化课程，并把讲解稿改写成自然口播稿。

两个阶段（对应参考方案）：
  1) structure_course : 文案 -> 课程大纲 / 每页标题 / 要点 / 每个要点的讲解稿
  2) polish_narration : 把讲解稿改写成更适合 AI 朗读的自然中文口播稿

无 OPENAI_API_KEY 时自动退化为纯规则实现，保证离线可演示。
"""
from __future__ import annotations

import json
import re
from typing import Optional

from .config import settings
from .models import Course, Slide, Segment

# 记录最近一次结构化是否真正用上了 LLM（供上层提示降级）
LAST_STATUS = {"llm": False, "note": ""}


# --------------------------------------------------------------------------- #
# OpenAI 客户端（惰性创建）
# --------------------------------------------------------------------------- #
def _client():
    from openai import OpenAI

    return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)


def _chat_json(system: str, user: str) -> dict:
    """调用 LLM 并强制返回 JSON 对象。"""
    client = _client()
    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "{}"
    return json.loads(content)


# --------------------------------------------------------------------------- #
# 阶段 1：结构化拆解
# --------------------------------------------------------------------------- #
_STRUCTURE_SYSTEM = """你是一名资深课程设计师，擅长把一篇上课文案拆解成结构清晰、适合 PPT 展示的课件。
请严格输出 JSON，不要包含任何多余文字。"""

_STRUCTURE_USER_TMPL = """请把下面这篇上课文案拆解成一套课程 PPT 结构。

要求：
1. 提炼课程标题(title)与副标题(subtitle)。
2. 生成 6~10 页幻灯片(slides)。第一页 kind 为 "cover"(封面)，最后一页 kind 为 "summary"(总结)，中间为 "content"。
3. 每页(除封面外)给出：
   - title: 简洁的页面标题(不超过 16 字)
   - bullets: 2~4 条要点，每条精炼短句(不超过 22 字)，是这一页 PPT 上真正展示的文字
   - intro_script: 进入这一页时的一句过渡讲解(口语、自然)
   - bullet_scripts: 与 bullets 一一对应的讲解稿，每条 1~3 句，把该要点讲透
4. 封面页 bullets 可为空，intro_script 为课程开场白，bullet_scripts 为空数组。
5. 讲解稿要口语化、有讲课感，不要照抄要点文字。

只输出如下 JSON 结构：
{
  "title": "...",
  "subtitle": "...",
  "slides": [
    {"kind":"cover","title":"...","bullets":[],"intro_script":"...","bullet_scripts":[]},
    {"kind":"content","title":"...","bullets":["...","..."],"intro_script":"...","bullet_scripts":["...","..."]}
  ]
}

文案如下：
\"\"\"
{script}
\"\"\""""


def structure_course(text: str) -> Course:
    if settings.llm_available():
        try:
            data = _chat_json(_STRUCTURE_SYSTEM, _STRUCTURE_USER_TMPL.replace("{script}", text.strip()))
            course = _course_from_struct(data)
            if not course.slides:
                raise ValueError("LLM 返回空结构（可能模型只输出了思考内容）")
            LAST_STATUS.update(llm=True, note="")
            return course
        except Exception as e:  # 出错回退规则法，保证流程不中断
            print(f"[llm] 结构化调用失败，回退规则法: {e}")
            LAST_STATUS.update(llm=False, note=f"LLM 拆解失败，已用规则兜底：{e}")
            return _rule_based_structure(text)
    LAST_STATUS.update(llm=False, note="未配置 OPENAI_API_KEY，已用规则兜底拆解")
    return _rule_based_structure(text)


def _course_from_struct(data: dict) -> Course:
    course = Course(title=data.get("title", "课程讲解"), subtitle=data.get("subtitle", ""))
    for i, s in enumerate(data.get("slides", [])):
        bullets = list(s.get("bullets", []) or [])
        bullet_scripts = list(s.get("bullet_scripts", []) or [])
        # 对齐长度，避免越界
        while len(bullet_scripts) < len(bullets):
            bullet_scripts.append(bullets[len(bullet_scripts)])
        segments = []
        intro = (s.get("intro_script") or "").strip()
        if intro:
            segments.append(Segment(kind="intro", script=intro))
        for bi, bs in enumerate(bullet_scripts[: len(bullets)]):
            segments.append(Segment(kind="bullet", script=bs.strip(), bullet_index=bi))
        course.slides.append(
            Slide(
                title=s.get("title", course.title if i == 0 else f"第 {i} 节"),
                bullets=bullets,
                segments=segments,
                index=i,
                kind=s.get("kind", "cover" if i == 0 else "content"),
            )
        )
    return course


# --------------------------------------------------------------------------- #
# 阶段 2：口播稿改写
# --------------------------------------------------------------------------- #
_POLISH_SYSTEM = """你是一名专业的课程配音导演，负责把书面讲解稿改写成适合 AI 语音朗读的中文口播稿。
请严格输出 JSON。"""

_POLISH_USER_TMPL = """把下面这组讲解稿改写成自然、流畅、有讲课感的中文口播稿。

改写要求：
- 口语化，像老师在课堂上娓娓道来；
- 合理断句，必要处用逗号制造停顿，让语音更自然；
- 适当加入"那么/接下来/我们可以看到/其实"等口语衔接词；
- 含义不变，不要加入要点之外的新信息；
- 每条长度与原文相近，不要明显变长。

输入是一个字符串数组，请按相同顺序输出改写后的数组：
{"scripts": ["...","..."]}

原始讲解稿数组：
{items}"""


def polish_narration(course: Course) -> Course:
    """把整门课所有 segment 的口播稿统一改写（一次调用，按页处理以控长度）。"""
    if not settings.llm_available():
        return course  # 规则法产出的稿子本身取自原文，已足够自然

    for slide in course.slides:
        scripts = [seg.script for seg in slide.segments]
        if not scripts:
            continue
        try:
            data = _chat_json(
                _POLISH_SYSTEM,
                _POLISH_USER_TMPL.replace("{items}", json.dumps(scripts, ensure_ascii=False)),
            )
            polished = data.get("scripts", scripts)
            if isinstance(polished, list) and len(polished) == len(scripts):
                for seg, new in zip(slide.segments, polished):
                    if isinstance(new, str) and new.strip():
                        seg.script = new.strip()
        except Exception as e:
            print(f"[llm] 口播改写失败(第{slide.index}页)，保留原稿: {e}")
    return course


# --------------------------------------------------------------------------- #
# 规则兜底：无 LLM 时把文案切成结构
# --------------------------------------------------------------------------- #
def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?；;])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _rule_based_structure(text: str) -> Course:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    if not blocks:
        blocks = [text.strip()]

    # 第一行作为标题
    first_line = blocks[0].splitlines()[0].strip()
    title = first_line if len(first_line) <= 30 else "课程讲解"
    course = Course(title=title, subtitle="AI 自动生成课程")

    # 封面
    cover_intro = "同学们好，欢迎来到本节课程，下面我们正式开始。"
    if len(blocks) > 1:
        cover_intro = _split_sentences(blocks[1])[0] if _split_sentences(blocks[1]) else cover_intro
    course.slides.append(
        Slide(title=title, bullets=[], segments=[Segment(kind="intro", script=cover_intro)], index=0, kind="cover")
    )

    # 内容页：每个段落一页
    content_blocks = blocks[1:] if len(blocks) > 1 else blocks
    idx = 1
    for block in content_blocks:
        sentences = _split_sentences(block)
        if not sentences:
            continue
        # 标题取段落首句的核心，要点取后续句子（最多4条）
        page_title = _short_title(sentences[0])
        body = sentences[1:] if len(sentences) > 1 else sentences
        bullets_src = body[:4] if len(body) >= 2 else sentences[:4]
        bullets = [_to_bullet(s) for s in bullets_src]
        segments = [Segment(kind="intro", script=sentences[0])]
        for bi, s in enumerate(bullets_src):
            segments.append(Segment(kind="bullet", script=s, bullet_index=bi))
        course.slides.append(
            Slide(title=page_title, bullets=bullets, segments=segments, index=idx, kind="content")
        )
        idx += 1

    # 标记最后一页为总结
    if len(course.slides) > 1:
        course.slides[-1].kind = "summary"
    return course


def _short_title(sentence: str) -> str:
    s = re.sub(r"[，,。.！!？?；;：:]", "", sentence)
    return s[:16] if len(s) > 16 else s


def _to_bullet(sentence: str) -> str:
    s = sentence.strip().rstrip("。.！!？?；;")
    return s[:22] + ("…" if len(s) > 22 else "")
