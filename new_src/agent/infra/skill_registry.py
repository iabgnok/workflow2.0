"""技能注册中心。

递归扫描 skills/llm/、skills/io/、skills/flow/ 子目录，
发现并注册所有实现了 execute_step 方法的技能类。
提供 build_skill_manifest() 生成供 LLM Prompt 注入的技能清单文本。
"""
from __future__ import annotations

import importlib
import inspect
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 需要递归扫描的技能子目录及其对应的模块前缀
_SKILL_SUBDIRS = [
    ("llm", "agent.skills.llm"),
    ("io", "agent.skills.io"),
    ("flow", "agent.skills.flow"),
]


class SkillNotFoundError(Exception):
    """请求的技能未注册时抛出。"""


class SkillRegistry:
    """技能注册中心。

    递归扫描三个技能子目录，识别技能类（含 execute_step 方法），
    以技能 name 属性为键注册到内部字典。
    """

    def __init__(self) -> None:
        self._registry: dict[str, object] = {}

    # ── 扫描 ─────────────────────────────────────────────────────────────────

    def scan(self, skills_root: str) -> None:
        """递归扫描 skills_root 下的 llm/、io/、flow/ 子目录并注册技能。

        Args:
            skills_root: skills 包的根目录路径（包含 llm/、io/、flow/ 子目录）。
        """
        base_path = Path(skills_root)
        if not base_path.exists():
            logger.warning("技能根目录不存在，跳过扫描: %s", skills_root)
            return

        for subdir, module_prefix in _SKILL_SUBDIRS:
            sub_path = base_path / subdir
            if not sub_path.exists():
                logger.debug("技能子目录不存在，跳过: %s", sub_path)
                continue
            self._scan_subdir(sub_path, module_prefix)

    def _scan_subdir(self, sub_path: Path, module_prefix: str) -> None:
        """扫描单个子目录下的所有 .py 文件（不含 __init__ 等私有文件）。"""
        for file_path in sorted(sub_path.glob("*.py")):
            if file_path.name.startswith("_"):
                continue
            module_name = f"{module_prefix}.{file_path.stem}"
            try:
                module = importlib.import_module(module_name)
            except Exception as exc:
                logger.warning("加载技能模块失败 %s: %s", module_name, exc)
                continue

            skill_instance = self._build_instance(module, module_name)
            if skill_instance is None:
                continue

            skill_name = getattr(skill_instance, "name", None) or getattr(
                type(skill_instance), "__name__", file_path.stem
            )
            self._registry[skill_name] = skill_instance
            logger.info("✅ 注册技能: %s (来自 %s)", skill_name, module_name)

    def _build_instance(self, module, module_name: str) -> object | None:
        """从模块中构造技能实例。

        查找顺序：
        1. 模块内任意含 execute_step 方法的类。
        2. 模块顶层 execute / execute_step 可调用函数（包装为适配器）。
        """
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            if hasattr(cls, "execute_step") or hasattr(cls, "execute"):
                try:
                    return cls()
                except Exception as exc:
                    logger.warning("技能类实例化失败 %s: %s", cls.__name__, exc)
                    return None

        execute_fn = getattr(module, "execute", None)
        execute_step_fn = getattr(module, "execute_step", None)
        if callable(execute_fn) or callable(execute_step_fn):
            return _ModuleSkillAdapter(module)

        logger.warning("模块 %s 未找到可用技能入口", module_name)
        return None

    # ── 手动注册 ──────────────────────────────────────────────────────────────

    def register(self, name: str, skill_instance: object) -> None:
        """手动注册技能实例（支持测试注入和运行时动态注册）。"""
        self._registry[name] = skill_instance

    # ── 查询 ─────────────────────────────────────────────────────────────────

    def get(self, name: str) -> object:
        if name not in self._registry:
            raise SkillNotFoundError(
                f"技能 '{name}' 未注册。已注册技能: {self.get_names()}"
            )
        return self._registry[name]

    def contains(self, name: str) -> bool:
        return name in self._registry

    def get_names(self) -> list[str]:
        return sorted(self._registry.keys())

    def get_all(self) -> dict[str, object]:
        return dict(self._registry)

    # ── Manifest 生成 ─────────────────────────────────────────────────────────

    def build_skill_manifest(self) -> str:
        """生成结构化技能清单文本，供 LLM Prompt 注入。

        依赖技能类的 schema_summary() 方法（Skill 基类提供）。
        若技能类不实现 schema_summary，则回退为简单名称+类名描述。

        Returns:
            包含所有已注册技能元数据的多行文本。
        """
        if not self._registry:
            return "（当前没有已注册的技能）"

        sections: list[str] = []
        for name in sorted(self._registry.keys()):
            skill = self._registry[name]
            if hasattr(skill, "schema_summary") and callable(skill.schema_summary):
                try:
                    sections.append(skill.schema_summary())
                    continue
                except Exception as exc:
                    logger.warning("技能 %s schema_summary() 调用失败: %s", name, exc)
            # 回退：简单描述
            description = getattr(skill, "description", "") or getattr(type(skill), "__doc__", "") or ""
            sections.append(f"=== {name} ===\n描述: {description or '（无描述）'}")

        return "\n\n".join(sections)


# ── 模块适配器（兼容函数式技能）────────────────────────────────────────────────

class _ModuleSkillAdapter:
    """将模块顶层 execute/execute_step 函数包装为技能对象。"""

    def __init__(self, module) -> None:
        self.module = module
        # 尝试从模块获取 name 属性
        self.name = getattr(module, "name", module.__name__.rsplit(".", 1)[-1])

    async def execute(self, text, context):
        return await self.module.execute(text, context)

    async def execute_step(self, step, context):
        if hasattr(self.module, "execute_step"):
            return await self.module.execute_step(step, context)
        return await self.module.execute(step.get("content", ""), context)
