"""单元测试：protocol/utils.py（任务 1.4）"""

import pytest

from agent.engine.protocol.utils import extract_metadata_inputs, is_optional_var, normalize_var_name
from agent.engine.protocol.models import WorkflowModel


class TestNormalizeVarName:
    def test_template_with_optional_marker(self):
        assert normalize_var_name("{{  user_input? }}") == "user_input"

    def test_backtick_with_spaces(self):
        assert normalize_var_name("  `file_path`  ") == "file_path"

    def test_plain_name(self):
        assert normalize_var_name("requirement") == "requirement"

    def test_optional_plain(self):
        assert normalize_var_name("prev_defects?") == "prev_defects"

    def test_template_no_optional(self):
        assert normalize_var_name("{{ output_path }}") == "output_path"

    def test_empty_string(self):
        assert normalize_var_name("") == ""

    def test_only_whitespace(self):
        assert normalize_var_name("   ") == ""

    def test_template_inner_spaces(self):
        assert normalize_var_name("{{  my_var  }}") == "my_var"


class TestExtractMetadataInputs:
    def test_list_inputs(self):
        model = WorkflowModel.model_validate({
            "metadata": {"inputs": ["requirement", "output_path?"]},
            "steps": [],
        })
        result = extract_metadata_inputs(model)
        assert result == {"requirement", "output_path"}

    def test_dict_inputs(self):
        model = WorkflowModel.model_validate({
            "metadata": {"inputs": {"requirement": "requirement", "output_path?": "output_path?"}},
            "steps": [],
        })
        result = extract_metadata_inputs(model)
        assert "requirement" in result
        assert "output_path" in result

    def test_empty_inputs(self):
        model = WorkflowModel.model_validate({"metadata": {"inputs": []}, "steps": []})
        assert extract_metadata_inputs(model) == set()

    def test_template_inputs(self):
        model = WorkflowModel.model_validate({
            "metadata": {"inputs": ["{{ requirement }}", "output_path?"]},
            "steps": [],
        })
        result = extract_metadata_inputs(model)
        assert "requirement" in result
        assert "output_path" in result


class TestIsOptionalVar:
    def test_optional_var(self):
        assert is_optional_var("prev_defects?") is True

    def test_required_var(self):
        assert is_optional_var("requirement") is False

    def test_empty_string(self):
        assert is_optional_var("") is False

    def test_only_question_mark(self):
        assert is_optional_var("?") is True

    def test_template_optional_at_end(self):
        # is_optional_var 检查原始末尾是否为 ?，模板写法末尾不是 ?
        assert is_optional_var("{{ var? }}") is False
        assert is_optional_var("var?") is True
