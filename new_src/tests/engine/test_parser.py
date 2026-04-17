"""单元测试：WorkflowParser（任务 6.3）"""
from __future__ import annotations

import json
import textwrap
import pytest
from unittest.mock import mock_open, patch

from agent.engine.parser import WorkflowParser, WorkflowParseError


# ── replace_variables ──────────────────────────────────────────────────────────

def test_replace_variables_basic():
    result = WorkflowParser.replace_variables("Hello {{name}}!", {"name": "World"})
    assert result == "Hello World!"


def test_replace_variables_missing_key_becomes_empty():
    result = WorkflowParser.replace_variables("{{missing}}", {})
    assert result == ""


def test_replace_variables_dict_serialized_as_json():
    result = WorkflowParser.replace_variables("{{data}}", {"data": {"k": "v"}})
    assert result == json.dumps({"k": "v"}, ensure_ascii=False)


def test_replace_variables_list_serialized_as_json():
    result = WorkflowParser.replace_variables("{{items}}", {"items": [1, 2, 3]})
    assert result == "[1, 2, 3]"


def test_replace_variables_no_double_substitution():
    """替换结果中的 {{...}} 不应被二次替换。"""
    result = WorkflowParser.replace_variables(
        "{{tmpl}}", {"tmpl": "{{raw}}", "raw": "BAD"}
    )
    assert result == "{{raw}}"


def test_replace_variables_integer_value():
    result = WorkflowParser.replace_variables("count={{n}}", {"n": 42})
    assert result == "count=42"


# ── parse() ───────────────────────────────────────────────────────────────────

SIMPLE_WF = textwrap.dedent("""\
    ---
    name: TestWF
    ---
    ## Step 1: Read File
    **Action**: `file_reader`
    **Inputs**:
    - file_path
    **Outputs**:
    - file_content
""")


def _parser_with_content(content: str) -> WorkflowParser:
    p = WorkflowParser("fake.step.md")
    with patch("builtins.open", mock_open(read_data=content)):
        p.parse()
    return p


def test_parse_step_count():
    p = _parser_with_content(SIMPLE_WF)
    assert len(p.steps) == 1


def test_parse_step_action():
    p = _parser_with_content(SIMPLE_WF)
    assert p.steps[0]["action"] == "file_reader"


def test_parse_step_inputs():
    p = _parser_with_content(SIMPLE_WF)
    assert "file_path" in p.steps[0]["inputs"]


def test_parse_step_outputs():
    p = _parser_with_content(SIMPLE_WF)
    assert "file_content" in p.steps[0]["outputs"]


def test_parse_metadata():
    p = _parser_with_content(SIMPLE_WF)
    assert p.metadata.get("name") == "TestWF"


def test_parse_file_not_found():
    p = WorkflowParser("nonexistent.step.md")
    with pytest.raises(WorkflowParseError, match="未找到"):
        p.parse()


def test_parse_on_reject_returns_int():
    content = textwrap.dedent("""\
        ---
        name: WF
        ---
        ## Step 1: Evaluate
        **Action**: `llm_evaluator_call`
        **on_reject**: `2`
        **Inputs**:
        - draft
        **Outputs**:
        - evaluator_report
    """)
    p = _parser_with_content(content)
    assert p.steps[0]["on_reject"] == 2
    assert isinstance(p.steps[0]["on_reject"], int)


def test_parse_condition_extracted():
    content = textwrap.dedent("""\
        ---
        name: WF
        ---
        ## Step 1: Conditional Step
        **Action**: `file_reader`
        **Condition**: `retry_count > 0`
        **Inputs**:
        - file_path
        **Outputs**:
        - result
    """)
    p = _parser_with_content(content)
    assert p.steps[0]["condition"] == "retry_count > 0"
