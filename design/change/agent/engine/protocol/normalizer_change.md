# protocol/normalizer.py 重构实现细节

## 一、整体方向

这个文件承担两类职责：数据归一化（normalize_parsed_data）和LLM 生成物文本清洗（normalize_generated_artifact、sanitize_artifact_for_engine）。前者是协议层的核心，后者是为了修复 LLM 生成 Markdown 不规范问题的补丁逻辑。重构后两者的地位发生变化。

## 二、normalize_parsed_data() 的保持

逻辑完整保留，这是 Parser 输出 dict → WorkflowModel 路径上的必要归一化步骤。
legacy on_reject 兼容层的生命周期：现有实现里 _extract_legacy_on_reject、_select_legacy_on_reject_target_index、以及把 frontmatter 级 on_reject 投影到步骤级的逻辑，是为了兼容旧版 .step.md 写法。根据 DSL 扫描报告（存档文档里），当前 dev/ 和 meta/ 里已经没有 frontmatter 级 on_reject 了。这套兼容逻辑保留但不新增使用，等到确认所有手写文件都已迁移后移除。触发时仍然在 ProtocolService.validate() 里发出 DSL_LEGACY_ON_REJECT_DEPRECATED warning。
_normalize_mapping 函数在 normalizer.py 里也有一份（和 models.py 里的相似但不完全一样）。这是历史遗留的复制。重构时两者都保留，注释说明它们各自的上下文（normalizer 里是处理 Parser 输出的 dict，models.py 里是处理 Pydantic validator 接收的输入），不强行合并以避免微妙的语义差异引入 bug。

## 三、sanitize_artifact_for_engine() 和 normalize_generated_artifact() 的命运

这两个函数是为了修复 LLM 生成的 Markdown 文本格式问题而存在的。重构后 LLM 生成物走结构化路径（Generator 直接输出 WorkflowModel），不再产生需要被这两个函数清洗的文本。
但不能立即删除：WorkflowRegistry 当前调用 sanitize_artifact_for_engine，以及在回放路径下（已持久化的 dev/ 文件），这两个函数仍然被间接用到。
处理方式：两个函数标注为 # Deprecated: will be removed after generator structured path is fully migrated，不再新增调用点，待 Generator 结构化路径完全打通且所有 dev/ 文件重新生成后，整块删除。