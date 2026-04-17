"""IO 技能单元测试。

覆盖：
- FileReader：从 step['inputs'] 映射解析路径、成功读取、路径缺失返回 {}、文件不存在抛出
- FileWriter：自动创建目录、内容写入、不做变量替换
"""
from __future__ import annotations

import os
import pytest

from agent.skills.io.file_reader import FileReader
from agent.skills.io.file_writer import FileWriter


# ── FileReader ─────────────────────────────────────────────────────────────

class TestFileReaderFromStepInputs:
    @pytest.mark.asyncio
    async def test_reads_path_from_inputs_mapping(self, tmp_path):
        """step['inputs']['file_path'] 指向 context 变量，应从中解析路径。"""
        target = tmp_path / "hello.txt"
        target.write_text("hello world", encoding="utf-8")

        skill = FileReader()
        step = {"inputs": {"file_path": "doc_path"}}
        context = {"doc_path": str(target)}
        result = await skill.execute_step(step, context)
        assert result["file_content"] == "hello world"

    @pytest.mark.asyncio
    async def test_fallback_to_file_path_key(self, tmp_path):
        """inputs 映射中无 file_path 时，回退为直接从 context 读取 file_path。"""
        target = tmp_path / "data.txt"
        target.write_text("data", encoding="utf-8")

        skill = FileReader()
        step = {"inputs": {}}
        context = {"file_path": str(target)}
        result = await skill.execute_step(step, context)
        assert result["file_content"] == "data"

    @pytest.mark.asyncio
    async def test_missing_path_returns_empty(self):
        """context 中找不到路径变量时，返回 {}（不抛出）。"""
        skill = FileReader()
        result = await skill.execute_step({"inputs": {}}, {})
        assert result == {}

    @pytest.mark.asyncio
    async def test_file_not_found_raises(self, tmp_path):
        """文件不存在时抛出 FileNotFoundError。"""
        skill = FileReader()
        step = {"inputs": {"file_path": "file_path"}}
        context = {"file_path": str(tmp_path / "nonexistent.txt")}
        with pytest.raises(FileNotFoundError):
            await skill.execute_step(step, context)

    @pytest.mark.asyncio
    async def test_returns_full_content(self, tmp_path):
        """返回文件完整内容字符串。"""
        content = "line1\nline2\nline3"
        target = tmp_path / "multi.txt"
        target.write_text(content, encoding="utf-8")

        skill = FileReader()
        step = {"inputs": {"file_path": "path"}}
        context = {"path": str(target)}
        result = await skill.execute_step(step, context)
        assert result["file_content"] == content


# ── FileWriter ────────────────────────────────────────────────────────────

class TestFileWriterAutoCreateDir:
    @pytest.mark.asyncio
    async def test_creates_nested_directories(self, tmp_path):
        """目标目录不存在时，自动创建完整目录链。"""
        output_path = tmp_path / "deep" / "nested" / "output.txt"
        assert not output_path.parent.exists()

        skill = FileWriter()
        step = {"content": "hello", "inputs": {}}
        context = {"target_file": str(output_path)}
        result = await skill.execute_step(step, context)

        assert output_path.exists()
        assert output_path.read_text(encoding="utf-8") == "hello"
        assert result["file_writer_status"] == "Success"

    @pytest.mark.asyncio
    async def test_writes_content_as_is(self, tmp_path):
        """写入内容不做二次变量替换。"""
        output_path = tmp_path / "out.txt"
        raw_content = "{{unchanged_var}} 保持原样"

        skill = FileWriter()
        step = {"content": raw_content, "inputs": {}}
        context = {"target_file": str(output_path), "unchanged_var": "SHOULD_NOT_REPLACE"}
        await skill.execute_step(step, context)

        written = output_path.read_text(encoding="utf-8")
        assert written == raw_content  # 不应被替换

    @pytest.mark.asyncio
    async def test_uses_inputs_mapping_for_target_path(self, tmp_path):
        """step['inputs']['target_file'] 映射应优先于 context 直接键。"""
        output_path = tmp_path / "mapped.txt"

        skill = FileWriter()
        step = {"content": "mapped content", "inputs": {"target_file": "output_path_var"}}
        context = {"output_path_var": str(output_path)}
        await skill.execute_step(step, context)

        assert output_path.read_text(encoding="utf-8") == "mapped content"

    @pytest.mark.asyncio
    async def test_overwrites_existing_file(self, tmp_path):
        """目标文件已存在时，覆盖写入。"""
        output_path = tmp_path / "existing.txt"
        output_path.write_text("old content", encoding="utf-8")

        skill = FileWriter()
        step = {"content": "new content", "inputs": {}}
        context = {"target_file": str(output_path)}
        await skill.execute_step(step, context)

        assert output_path.read_text(encoding="utf-8") == "new content"
