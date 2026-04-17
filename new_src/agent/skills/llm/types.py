"""LLM 技能层共享类型定义。

Decision 5 (design.md): EvaluatorReport / Defect / StructuredWorkflowArtifact 放在此处。
这些类型描述 LLM 评审结果与生成契约的业务语义，属于技能层而非协议层。
"""
from __future__ import annotations

from typing import Annotated, List, Literal

from pydantic import AfterValidator, BaseModel, Field


# ── StructuredWorkflowArtifact ─────────────────────────────────────────────
# Generator 强制 LLM 输出的结构化格式。action 字段使用 AfterValidator 做动态校验，
# 而非 Literal 枚举——因为技能列表在运行时由 SkillRegistry 确定。

def _validate_action(v: str) -> str:
    """确保 action 字段非空（白名单校验在 Generator._validate_actions() 中完成）。"""
    v = v.strip() if v else ""
    if not v:
        raise ValueError("step action 不能为空字符串")
    return v


class WorkflowStepSpec(BaseModel):
    name: str = Field(description="步骤名称")
    action: Annotated[str, AfterValidator(_validate_action)] = Field(
        description="步骤 action（必须属于已注册技能列表）"
    )
    inputs: list[str] = Field(default_factory=list, description="步骤输入变量列表")
    outputs: list[str] = Field(default_factory=list, description="步骤输出变量列表")
    condition: str | None = Field(default=None, description="可选条件表达式")
    workflow: str | None = Field(default=None, description="sub_workflow_call 时的子流程路径")
    on_reject: int | None = Field(default=None, description="可选回跳步号")
    require_confirm: bool = Field(default=False, description="高风险动作是否需要 [CONFIRM]")


class StructuredWorkflowArtifact(BaseModel):
    workflow_name: str = Field(description="工作流名称")
    description: str = Field(default="", description="工作流描述")
    inputs: list[str] = Field(default_factory=list, description="frontmatter 输入变量列表")
    outputs: list[str] = Field(default_factory=list, description="frontmatter 输出变量列表")
    steps: list[WorkflowStepSpec] = Field(default_factory=list, description="结构化步骤列表")
    explanation: str = Field(description="生成说明")


# ── EvaluatorReport / Defect ──────────────────────────────────────────────
# Evaluator 技能的输出类型，也是 Generator 重试的驱动数据。

class Defect(BaseModel):
    location: str = Field(description="错误发生坐标，如 'Step 4: 生成报告'")
    type: Literal["LOGIC_ERROR", "SAFETY_VIOLATION", "QUALITY_ISSUE", "STYLE_ISSUE"] = Field(
        description="错误分类"
    )
    reason: str = Field(description="打回原因的详细说明")
    suggestion: str = Field(description="可执行的局部修改建议")


class EvaluatorReport(BaseModel):
    status: Literal["APPROVED", "REJECTED"] = Field(description="严格输出：APPROVED 或 REJECTED")
    score: int = Field(ge=0, le=100, description="0-100 四维加权总分")
    dimension_scores: dict = Field(
        default_factory=dict,
        description="四维分项得分：logic_closure, safety_gate, engineering_quality, persona_adherence",
    )
    defects: List[Defect] = Field(
        default_factory=list,
        description="所有发现的缺陷列表，APPROVED 时为空列表",
    )
    overall_feedback: str = Field(description="总体评价，REJECTED 时明确说明修复方向")
