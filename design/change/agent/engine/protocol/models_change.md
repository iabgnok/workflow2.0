# protocol/models.py 重构实现细节

## 一、整体定位不变，有两处扩展

WorkflowModel、WorkflowMetadata、WorkflowStep 是协议层的内部唯一真理，这个定位保持。重构后增加两类内容：RunResult 类型和从 StructuredWorkflowArtifact 直接构建的方法。

## 二、WorkflowStep 的改动

现有字段全部保持：id、name、content、action、workflow、condition、on_reject、inputs、outputs。类型定义不变。
新增 require_confirm: bool = False 字段，对应 DSL 里 **Action**: \skill_name` [CONFIRM]标记。当前这个标记在 Parser 的_extract_action()` 里被清除掉了，用于安全扫描的 [CONFIRM] 检查是在 security_scan 里做的文本扫描。重构后统一把这个信息记录到 StepModel 里，Parser 解析 [CONFIRM] 标记时写入此字段，security_scan 直接读 StepModel 字段判断而不是再做文本扫描。[待定：Parser 改动时序]
model_config = ConfigDict(extra="allow") 保持，允许额外字段（协议层向上兼容）。

## 三、WorkflowModel 新增方法

1. from_structured_artifact(artifact: StructuredWorkflowArtifact) -> WorkflowModel：
    这是方向一的关键适配器。StructuredWorkflowArtifact 是 Generator 的 Pydantic 输出类型，这个类方法把它直接转换成 WorkflowModel，不经过任何 Markdown 渲染。具体转换：artifact.steps 里每个 WorkflowStepSpec 转成 WorkflowStep，artifact.workflow_name / artifact.inputs / artifact.outputs 组成 WorkflowMetadata。[待定：StructuredWorkflowArtifact 定义的确切位置，目前在 skills/llm/generator.py 里，转换方法放在 models.py 里意味着 models.py 需要 import generator，这会造成依赖倒置。更好的方式是把转换函数放在 generator.py 里作为 to_workflow_model() 方法，或者在 protocol/service.py 里做适配。此处 [待定]]
2. to_markdown() -> str：
    将 WorkflowModel 渲染为标准 .step.md 格式文本。这是持久化到 dev/ 目录时需要的功能，当前分散在 LLMGeneratorCall._render_markdown() 里（属于 skill 层，不合适）和 normalizer 里。统一放到 WorkflowModel 上是最合理的——"我知道自己的格式，我负责把自己渲染出来"。渲染规则和现有 _render_markdown() 完全一致，只是搬移位置。
3. RunResult Pydantic 类：
    新增在同文件底部（或独立的 engine/models.py）。字段：run_id: str、status: Literal["success", "failed", "escalation_exceeded"]、context: dict[str, Any]、workflow_name: str。替代 Runner 当前返回的 plain dict。[待定：RunResult 放在 protocol/models.py 还是 engine/models.py，倾向于 engine/models.py 以保持协议层纯粹性]

## 四、_normalize_mapping 等内部工具函数

models.py 里定义了 _normalize_mapping、_normalize_io_list_or_map、_normalize_optional_text 三个模块级私有函数。这三个函数是 Pydantic validator 使用的内部工具，不对外暴露，保持在 models.py 里（不迁入 utils.py）。原因：它们的上下文是"如何把原始输入归一化为模型字段"，和 utils.py 的上下文（"如何在协议检查逻辑里处理变量名"）是两件不同的事。