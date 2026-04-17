"""工作流解析器：只负责手写 .step.md 文件的解析。

LLM 生成物走 Generator → WorkflowModel 的结构化路径，不经过此类。
"""
from __future__ import annotations

import json
import logging
import re

import yaml

logger = logging.getLogger(__name__)


class WorkflowParseError(Exception):
    """工作流解析过程中发生的异常。"""


class WorkflowParser:
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.raw_content = ""
        self.metadata: dict = {}
        self.steps: list[dict] = []

    def parse(self) -> dict:
        try:
            with open(self.filepath, encoding="utf-8") as f:
                self.raw_content = f.read()
        except FileNotFoundError:
            raise WorkflowParseError(f"工作流文件未找到: {self.filepath}")
        except Exception as exc:
            raise WorkflowParseError(f"读取工作流文件失败 {self.filepath}: {exc}")

        # ── 第一阶段：YAML frontmatter ────────────────────────────────────
        yaml_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", self.raw_content, re.DOTALL)
        if yaml_match:
            try:
                self.metadata = yaml.safe_load(yaml_match.group(1)) or {}
            except yaml.YAMLError as exc:
                raise WorkflowParseError(
                    f"{self.filepath} 中存在无效的 YAML frontmatter: {exc}"
                )
            body = self.raw_content[yaml_match.end():]
        else:
            self.metadata = {}
            body = self.raw_content

        # ── 第二阶段：按步骤块切割 ────────────────────────────────────────
        raw_steps = re.split(r"(?m)^## Step\s+\d+", body)

        self.steps = []
        for i, content in enumerate(raw_steps[1:], 1):
            self.steps.append(
                {
                    "id": i,
                    "name": self._extract_step_name(content),
                    "content": content.strip(),
                    "action": self._extract_action(content),
                    "workflow": self._extract_workflow(content),
                    "condition": self._extract_condition(content),
                    "on_reject": self._extract_on_reject(content),
                    "inputs": self._extract_io(content, "Input"),
                    "outputs": self._extract_io(content, "Output"),
                }
            )

        return {"metadata": self.metadata, "steps": self.steps}

    # ── 私有解析方法 ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_markdown_scalar(
        content: str, field_name: str, strip_inline_comment: bool = False
    ) -> str | None:
        pattern = rf"(?im)^\s*\*\*{field_name}\*\*:\s*`?(.*?)`?\s*$"
        match = re.search(pattern, content)
        if not match:
            return None
        text = match.group(1).strip().strip("`").strip()
        if strip_inline_comment:
            text = re.sub(r"\s+#.*$", "", text).strip()
        return text or None

    def _extract_step_name(self, content: str) -> str:
        first_line = content.strip().split("\n")[0]
        if ":" in first_line:
            return first_line.split(":", 1)[1].strip()
        return first_line.strip()

    def _extract_action(self, content: str) -> str:
        explicit = re.search(r"(?im)^\s*\*\*Action\*\*:\s*`([^`]+)`", content)
        action = (
            explicit.group(1).strip()
            if explicit
            else self._extract_markdown_scalar(content, "Action", strip_inline_comment=True)
        )
        if action:
            action = re.sub(
                r"\s+\[(?:CONFIRM|DANGER)\]\s*$", "", action, flags=re.IGNORECASE
            ).strip()
        return action or "unknown"

    def _extract_workflow(self, content: str) -> str | None:
        return self._extract_markdown_scalar(content, "Workflow")

    def _extract_condition(self, content: str) -> str | None:
        return self._extract_markdown_scalar(content, "Condition")

    def _extract_on_reject(self, content: str) -> int | None:
        match = re.search(
            r"(?im)^\s*\*\*on[\s_-]?reject\*\*:\s*`?(\d+)`?\s*$", content
        )
        return int(match.group(1)) if match else None

    def _extract_io(self, content: str, io_type: str) -> dict:
        regex = rf"(?im)^\s*\*\*{io_type}s?\*\*:\s*(?:\r?\n)((?:\s*-.*(?:\r?\n|$))*)"
        match = re.search(regex, content)
        if not match:
            return {}
        result = {}
        for raw in match.group(1).strip().split("\n"):
            clean = re.sub(r"\s*#.*$", "", raw)
            clean = re.sub(r"^\s*-\s*", "", clean).strip()
            if not clean:
                continue
            if ":" in clean:
                k, v = clean.split(":", 1)
                result[k.strip()] = v.strip()
            else:
                result[clean] = clean
        return result

    # ── 变量注入（保留静态方法）───────────────────────────────────────────

    @staticmethod
    def replace_variables(text: str, variables: dict) -> str:
        """
        将 text 中的 {{var}} 占位符一次性替换为 variables 中的值。

        - dict/list → JSON 字符串
        - 其他类型 → str()
        - 未找到的占位符 → 空字符串（降级容错）
        """
        def _replacer(match: re.Match) -> str:
            key = match.group(1)
            val = variables.get(key)
            if val is None:
                logger.debug("变量 {{%s}} 在 context 中未找到，替换为空字符串", key)
                return ""
            if isinstance(val, (dict, list)):
                return json.dumps(val, ensure_ascii=False)
            return str(val)

        return re.sub(r"\{\{([a-zA-Z_][a-zA-Z0-9_.]*)\}\}", _replacer, text)
