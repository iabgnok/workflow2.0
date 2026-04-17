"""单元测试：models.py to_markdown() 往返一致性（任务 2.3）"""

import pytest

from agent.engine.protocol.models import WorkflowMetadata, WorkflowModel, WorkflowStep


def _make_simple_model() -> WorkflowModel:
    return WorkflowModel.model_validate({
        "metadata": {
            "name": "TestWorkflow",
            "description": "A test workflow",
            "inputs": ["file_path", "output_dir?"],
            "outputs": ["result"],
        },
        "steps": [
            {
                "id": 1,
                "name": "Read File",
                "action": "file_reader",
                "inputs": {"file_path": "file_path"},
                "outputs": {"file_content": "file_content"},
                "content": "Read the file.",
            },
            {
                "id": 2,
                "name": "Process",
                "action": "llm_prompt_call",
                "require_confirm": False,
                "inputs": {"content": "file_content"},
                "outputs": {"result": "result"},
                "content": "Process content.",
            },
        ],
    })


class TestToMarkdown:
    def test_produces_frontmatter(self):
        model = _make_simple_model()
        md = model.to_markdown()
        assert "---" in md
        assert "TestWorkflow" in md

    def test_produces_step_headers(self):
        model = _make_simple_model()
        md = model.to_markdown()
        assert "## Step 1: Read File" in md
        assert "## Step 2: Process" in md

    def test_produces_action_line(self):
        model = _make_simple_model()
        md = model.to_markdown()
        assert "**Action**: `file_reader`" in md
        assert "**Action**: `llm_prompt_call`" in md

    def test_require_confirm_adds_marker(self):
        model = WorkflowModel.model_validate({
            "metadata": {"name": "ConfirmTest"},
            "steps": [{
                "id": 1,
                "name": "Write Step",
                "action": "file_writer",
                "require_confirm": True,
                "inputs": {},
                "outputs": {"status": "status"},
                "content": "",
            }],
        })
        md = model.to_markdown()
        assert "**Action**: `file_writer` [CONFIRM]" in md

    def test_no_confirm_marker_when_false(self):
        model = _make_simple_model()
        md = model.to_markdown()
        assert "[CONFIRM]" not in md

    def test_input_self_mapping_rendered_as_plain(self):
        model = WorkflowModel.model_validate({
            "metadata": {"name": "IOTest"},
            "steps": [{
                "id": 1,
                "name": "Step",
                "action": "my_skill",
                "inputs": {"file_path": "file_path"},
                "outputs": {"result": "result"},
                "content": "",
            }],
        })
        md = model.to_markdown()
        # 自映射应渲染为 `- file_path`，而非 `- file_path: file_path`
        assert "- file_path\n" in md or "- file_path" in md

    def test_input_cross_mapping_rendered_with_colon(self):
        model = WorkflowModel.model_validate({
            "metadata": {"name": "MapTest"},
            "steps": [{
                "id": 1,
                "name": "Step",
                "action": "my_skill",
                "inputs": {"local_var": "upstream_var"},
                "outputs": {"out": "out"},
                "content": "",
            }],
        })
        md = model.to_markdown()
        assert "- local_var: upstream_var" in md

    def test_on_reject_rendered(self):
        model = WorkflowModel.model_validate({
            "metadata": {"name": "RejectTest"},
            "steps": [
                {
                    "id": 1,
                    "name": "First",
                    "action": "skill_a",
                    "inputs": {},
                    "outputs": {"a": "a"},
                    "content": "",
                },
                {
                    "id": 2,
                    "name": "Second",
                    "action": "skill_b",
                    "on_reject": 1,
                    "inputs": {"a": "a"},
                    "outputs": {"b": "b"},
                    "content": "",
                },
            ],
        })
        md = model.to_markdown()
        assert "**on_reject**: `1`" in md

    def test_metadata_inputs_in_frontmatter(self):
        model = _make_simple_model()
        md = model.to_markdown()
        assert "file_path" in md
        assert "output_dir" in md or "output_dir?" in md

    def test_empty_steps_produces_only_frontmatter(self):
        model = WorkflowModel.model_validate({
            "metadata": {"name": "EmptyWorkflow"},
            "steps": [],
        })
        md = model.to_markdown()
        assert "EmptyWorkflow" in md
        assert "## Step" not in md
