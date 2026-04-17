"""
技能基类模块。

定义 MyWorkflow 技能体系的类型层次：
  Skill[InputT, OutputT]     —— 泛型基类，所有技能的统一接口
  ├── LLMAgentSpec           —— LLM 类技能公共基类（结构化输出 + Prompt 缓存）
  ├── IOSkillSpec            —— IO 类技能语义分组基类
  └── FlowSkillSpec          —— 流程类技能语义分组基类
"""
from __future__ import annotations

import enum
import os
from dataclasses import dataclass, field
from typing import Any, ClassVar, Generic, Optional, Type, TypeVar

from pydantic import BaseModel

from config.settings import settings

# ── 类型变量 ──────────────────────────────────────────────────────────────
InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


# ── 幂等性枚举 ─────────────────────────────────────────────────────────────

class IdempotencyLevel(str, enum.Enum):
    L0 = "L0"   # 完全幂等，无副作用（读操作）
    L1 = "L1"   # 有副作用，但重试安全（幂等写）
    L2 = "L2"   # 非幂等，重试可能产生副作用（状态变更）


# ── 重试策略 ───────────────────────────────────────────────────────────────

@dataclass
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: float = 1.0
    enabled: bool = True


_DEFAULT_RETRY_POLICY = RetryPolicy()


# ── 泛型技能基类 ──────────────────────────────────────────────────────────

class Skill(Generic[InputT, OutputT]):
    """MyWorkflow 技能统一基类。

    子类通过类变量声明自身元数据，并实现 ``execute_step(step, context)`` 作为运行入口。
    SkillRegistry 读取这些类变量完成自动注册、策略查找和 Manifest 生成。
    """

    # ── 子类必须声明的元数据 ──────────────────────────────────────────────
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    when_to_use: ClassVar[str] = ""
    do_not_use_when: ClassVar[str] = ""
    idempotency: ClassVar[IdempotencyLevel] = IdempotencyLevel.L1
    retry_policy: ClassVar[RetryPolicy] = _DEFAULT_RETRY_POLICY
    input_type: ClassVar[Optional[Type[BaseModel]]] = None
    output_type: ClassVar[Optional[Type[BaseModel]]] = None

    # ── SkillCard 生成 ────────────────────────────────────────────────────

    @classmethod
    def schema_summary(cls) -> str:
        """生成供 LLM Prompt 注入的 SkillCard 文本。

        内容包含技能名称、描述、使用场景和输入输出字段说明。
        """
        lines: list[str] = [f"=== {cls.name or cls.__name__} ==="]
        if cls.description:
            lines.append(f"描述: {cls.description}")
        if cls.when_to_use:
            lines.append(f"使用场景: {cls.when_to_use}")
        if cls.do_not_use_when:
            lines.append(f"不适用场景: {cls.do_not_use_when}")

        idempotency_val = (
            cls.idempotency.value
            if isinstance(cls.idempotency, IdempotencyLevel)
            else str(cls.idempotency)
        )
        lines.append(f"幂等性: {idempotency_val}")

        if cls.input_type is not None:
            lines.append("输入字段:")
            for fname, finfo in cls.input_type.model_fields.items():
                ann = finfo.annotation
                type_name = getattr(ann, "__name__", str(ann))
                desc = finfo.description or ""
                lines.append(f"  - {fname}: {type_name}" + (f"  # {desc}" if desc else ""))

        if cls.output_type is not None:
            lines.append("输出字段:")
            for fname, finfo in cls.output_type.model_fields.items():
                ann = finfo.annotation
                type_name = getattr(ann, "__name__", str(ann))
                desc = finfo.description or ""
                lines.append(f"  - {fname}: {type_name}" + (f"  # {desc}" if desc else ""))

        return "\n".join(lines)

    # ── 运行入口（子类实现）──────────────────────────────────────────────

    async def execute_step(self, step: dict, context: dict) -> dict:
        raise NotImplementedError(
            f"{self.__class__.__name__} 未实现 execute_step(step, context)。"
        )


# ── LLM 类技能基类 ────────────────────────────────────────────────────────

class LLMAgentSpec(Skill[InputT, OutputT]):
    """LLM 技能规范基类。

    提供两个公共方法供所有 LLM 技能复用：
    - ``_get_structured_llm(schema)``：构建按 Pydantic schema 输出的结构化 LLM 客户端。
    - ``_load_system_prompt()``：从 ``settings.prompts_root`` 读取外部 Prompt 文件（带缓存）。

    子类需设置：
    - ``system_prompt_path``：相对于 ``prompts_root`` 的文件路径。
    - ``default_temperature``：LLM 采样温度，默认 0.1。
    """

    system_prompt_path: ClassVar[str] = ""
    default_temperature: ClassVar[float] = 0.1

    def __init__(self) -> None:
        # 实例级缓存：key = 绝对路径，value = 文件内容字符串
        self._prompt_cache: dict[str, str] = {}

    # ── 结构化 LLM 工厂 ──────────────────────────────────────────────────

    def _get_structured_llm(self, schema: Any) -> Any:
        """构建按 ``schema`` 强制输出的结构化 LLM 客户端。

        延迟导入 llm_factory，兼容 old_src 混用期。
        后续 infra-layer-extract 变更将把工厂函数迁移至 agent.infra。

        Args:
            schema: Pydantic BaseModel 子类，定义 LLM 输出结构。

        Returns:
            LangChain structured-output runnable。
        """
        from agent.infra.llm_factory import (
            build_chat_model,
            build_structured_output_model,
        )
        llm = build_chat_model(temperature=self.default_temperature)
        return build_structured_output_model(llm, schema)

    # ── Prompt 加载与缓存 ─────────────────────────────────────────────────

    def _load_system_prompt(self) -> str:
        """加载并缓存系统 Prompt 文件内容。

        Returns:
            系统 Prompt 的完整文本字符串。

        Raises:
            ValueError: 当 ``system_prompt_path`` 未设置时。
            FileNotFoundError: 当目标文件不存在时。
        """
        if not self.system_prompt_path:
            raise ValueError(
                f"{self.__class__.__name__} 未设置 system_prompt_path，"
                "无法加载系统 Prompt。"
            )

        prompts_root = settings.prompts_root or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "prompts")
        )
        abs_path = os.path.join(prompts_root, self.system_prompt_path)

        if abs_path not in self._prompt_cache:
            with open(abs_path, encoding="utf-8") as f:
                self._prompt_cache[abs_path] = f.read()

        return self._prompt_cache[abs_path]


# ── IO 类技能语义基类 ──────────────────────────────────────────────────────

class IOSkillSpec(Skill[InputT, OutputT]):
    """IO 类技能语义分组基类。

    FileReader、FileWriter 等文件系统操作技能继承此类，
    便于 SkillRegistry 按类别过滤和 Manifest 分类展示。
    """


# ── 流程类技能语义基类 ────────────────────────────────────────────────────

class FlowSkillSpec(Skill[InputT, OutputT]):
    """流程类技能语义分组基类。

    SubWorkflowCall 等工作流编排技能继承此类，
    标识该技能会触发子工作流执行，具有特殊的上下文隔离语义。
    """
