# protocol/security_scan.py 重构实现细节

## 一、删除 _scan_action_whitelist()

如 gatekeeper 分析里所述，action 白名单检查的唯一实现点是 Gatekeeper，_scan_action_whitelist 删除。
scan_artifact_security() 函数的签名改为去掉 registered_skills 参数，或者保留参数但内部不做 action 检查（只是忽略），保持接口向后兼容。倾向于保留参数签名但内部不调用 _scan_action_whitelist，这样现有调用方不需要改代码，只是该参数变成无效输入。[待定：是否清理参数还是静默忽略]

## 二、DANGER_KEYWORDS 和 CONFIRM_KEYWORDS 的管理

现有两个列表硬编码在文件里。长期来看应该从 settings.py 读取，允许在不改代码的情况下添加新的危险关键词。
重构时不动，这个改动不是必须的，但加注释说明未来可配置化方向。

## 三、扫描函数接受文本还是 WorkflowModel

现有 scan_artifact_security(artifact: str) 接受 Markdown 文本字符串。这是因为安全扫描是在注册流程里对原始文本做的。
重构后，如果 LLM 生成物走结构化路径（不产生 Markdown 文本），安全扫描需要在 WorkflowModel 上工作，而不是在文本上。WorkflowModel 里的 step.content 字段存储了步骤的全文内容，危险关键词可能出现在 content 里。
增加重载或新函数 scan_workflow_model(model: WorkflowModel) -> SecurityScanResult：遍历 model.steps，对每个 step.content 做关键词扫描，对 step.action 做 [CONFIRM] 标记检查（读取 step.require_confirm 字段）。原有的 scan_artifact_security() 保留用于处理已持久化的 .step.md 文件文本。两个函数都可以产生 SecurityScanResult。[待定：何时切换到 scan_workflow_model 取决于 Generator 结构化路径落地时机]