"""Prompt 契约回归测试。

防止 Generator/Planner prompt 回退到不兼容的输出契约。
"""
from __future__ import annotations

import os


def _read_prompt(filename: str) -> str:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    path = os.path.join(root, "prompts", filename)
    with open(path, encoding="utf-8") as f:
        return f.read()


def test_generator_prompt_is_schema_first_and_not_markdown_first() -> None:
    text = _read_prompt("generator_system_v1.md")

    # 正向约束：必须有结构化 schema 语义
    assert "StructuredWorkflowArtifact" in text
    assert "JSON" in text
    assert "action" in text
    assert "logic_closure" in text
    assert "safety_gate" in text

    # 反向约束：禁止回退到 markdown 产物模板
    assert "Frontmatter" not in text
    assert "## Step N" not in text
    assert "**Action**:" not in text


def test_planner_prompt_requires_registered_skills_whitelist() -> None:
    text = _read_prompt("planner_system_v1.md")
    assert "registered_skills" in text
    assert "action_type" in text
    assert "白名单" in text
    assert "必须从 `registered_skills` 中选择" in text
