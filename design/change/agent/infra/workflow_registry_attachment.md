# infra/workflow_registry.py（从 engine/workflow_registry.py 搬移）

## 一、register_workflow_model 新方法的实现细节

完整签名：register_workflow_model(model: WorkflowModel, description: str = "", registered_skills: list[str] | None = None, available_context: dict | None = None) -> dict。
内部流程：

    self.ensure_ready()（确保目录和 index 文件存在）
    protocol_service.validate_workflow_model(model, registered_skills, available_context) 做内存校验（不写文件）
    校验失败：直接抛异常（或返回失败结果），不写任何文件，no dirty write 保证
    校验通过：workflow_id = self._build_workflow_id(model.metadata.name)
    workflow_path = dev_dir / f"{workflow_id}.step.md"
    markdown_text = model.to_markdown()（调 WorkflowModel 的渲染方法）
    写文件：workflow_path.write_text(markdown_text, encoding="utf-8")
    写索引（原子写 .tmp → os.replace）
    返回包含 workflow_id、workflow_path、protocol_report、dry_run 的 dict

旧方法 register_generated_workflow(artifact: str, ...) 保留为兼容入口，内部先调 ProtocolService.parse_workflow_file() 解析文本，得到 WorkflowModel 后转调新方法，消除重复逻辑。

## 二、索引路径的调整

现有 index_path 是构造函数参数，指向 workflows/index.json。重构后 index 移到 workflows/registry/index.json，WorkflowRegistry 的默认 index_path 改为 settings.WORKFLOWS_REGISTRY_DIR / "index.json"，由 config/settings.py 统一管理路径。

## 三、_extract_name 的调整

现有 _extract_name(artifact: str) 用正则从 Markdown 文本里提取 name: 字段。新路径不需要这个方法（直接读 model.metadata.name），旧路径（兼容接口）仍然用到。保留，不删除。