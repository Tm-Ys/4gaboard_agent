import json
from typing import List
from langchain_core.messages import SystemMessage, HumanMessage
from .knowledge_base import llm_invoke
from .models import FeaturePoint, TestScenario, TestStep, TestExpectation
from src.retrieval.base import Retriever
from src.utils.log import logger


def _clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _parse_json_safe(text: str):
    cleaned = _clean_json(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    for brace in ("[", "{"):
        start = cleaned.find(brace)
        if start >= 0:
            try:
                return json.loads(cleaned[start:])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"Failed to parse LLM response as JSON: {cleaned[:200]}")


FEATURE_EXTRACTION_SYSTEM = (
    "你是一个软件测试分析师，正在分析一个名为「4ga Boards」的看板项目管理工具的用户手册。"
    "请从手册内容中提取主要功能点，每个功能点应该是用户可以独立操作的完整功能模块。\n\n"
    "要求：\n"
    "- 功能点粒度适中\n"
    "- 覆盖手册中提到的所有核心功能区域\n"
    "- 返回 JSON 数组，格式：\n"
    '[{"name": "功能点名称", "description": "功能点描述"}]'
)

FEATURE_RETRY_SYSTEM = (
    "上次输出的 JSON 格式有误，请严格按要求的 JSON 数组格式重新输出。"
    "只输出 JSON，不要额外文字。格式："
    '[{"name": "...", "description": "..."}]'
)

SCENARIO_SYSTEM_TEMPLATE = (
    "你是一个测试场景设计师，正在为「4ga Boards」看板项目管理工具设计测试场景。\n\n"
    "要求：\n"
    "- 每个功能点生成 2~4 个独立的测试场景\n"
    "- 场景覆盖：基本功能流程、异常/边界情况\n"
    "- 每一步操作必须具体、可被浏览器自动化执行\n"
    "- 预期结果必须可验证（页面变化、弹窗出现、数据变化等）\n"
    "- 参考以下文档上下文来确保场景的准确性\n\n"
    "返回 JSON 格式（必须严格遵循）：\n"
    '{{\n'
    '  "scenarios": [\n'
    '    {{\n'
    '      "name": "创建新项目",\n'
    '      "description": "验证用户可以通过侧边栏创建新项目",\n'
    '      "steps": [\n'
    '        {{"action": "点击侧边栏的添加按钮", "target": "sidebar add button"}},\n'
    '        {{"action": "输入项目名称", "target": "项目名称输入框"}},\n'
    '        {{"action": "点击创建按钮", "target": "创建按钮"}}\n'
    '      ],\n'
    '      "expectations": [\n'
    '        {{"description": "新项目出现在侧边栏列表中"}},\n'
    '        {{"description": "页面跳转到新项目的默认看板视图"}}\n'
    '      ]\n'
    '    }}\n'
    '  ]\n'
    '}}\n\n'
    "参考文档上下文：\n{context}"
)


def extract_features(doc_context: str, max_retries: int = 2) -> List[FeaturePoint]:
    messages = [
        SystemMessage(content=FEATURE_EXTRACTION_SYSTEM),
        HumanMessage(content=f"以下是用户手册各页面内容（标题 + 内容摘要）：\n\n{doc_context}"),
    ]

    for attempt in range(max_retries + 1):
        try:
            response = llm_invoke(messages)
            data = _parse_json_safe(response)
            items = data if isinstance(data, list) else data.get("features", data.get("功能点", []))
            result = [FeaturePoint(**item) for item in items]
            if result:
                return result
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            if attempt < max_retries:
                messages = [
                    SystemMessage(content=FEATURE_RETRY_SYSTEM),
                    HumanMessage(content=f"用户手册内容：\n{doc_context}"),
                ]
            else:
                raise ValueError(f"Feature extraction failed after {max_retries+1} attempts: {e}")
    return []


def generate_scenarios(feature: FeaturePoint, retriever: Retriever, max_retries: int = 2) -> FeaturePoint:
    docs = retriever.retrieve(feature.description, k=5)
    context = "\n\n---\n\n".join(
        f"[{d['title']}]({d['url']})\n{d['content'][:1500]}" for d in docs
    )
    system_msg = SCENARIO_SYSTEM_TEMPLATE.format(context=context)
    messages = [
        SystemMessage(content=system_msg),
        HumanMessage(content=f"请为功能点「{feature.name}」设计测试场景。\n功能描述：{feature.description}"),
    ]

    for attempt in range(max_retries + 1):
        try:
            response = llm_invoke(messages)
            data = _parse_json_safe(response)
            items = data if isinstance(data, list) else data.get("scenarios", [])
            scenarios = []
            for item in items:
                steps = [TestStep(**s) for s in item.get("steps", []) if s]
                expectations = [TestExpectation(**e) for e in item.get("expectations", []) if e]
                if steps or expectations:
                    scenarios.append(TestScenario(
                        name=item.get("name", ""),
                        description=item.get("description", ""),
                        steps=steps,
                        expectations=expectations,
                    ))
            if scenarios:
                feature.scenarios = scenarios
                return feature
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            if attempt == max_retries:
                logger.warning("scenario generation failed for '%s': %s", feature.name, e)
    return feature
