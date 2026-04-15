# workflow_registry.py → 移入 infra/ 重构实现细节

## 一、文件搬移

从 agent/engine/ 移入 agent/infra/，原因：它是文件系统和索引 JSON 的操作层，是基础设施，不是执行控制流。

## 二、最大的变化：注册入口

现有 register_generated_workflow(artifact: str, ...) 接受的是 Markdown 字符串。重构后主注册路径接受 WorkflowModel Pydantic 对象（方向一落地后）：
   register_workflow_model(model: WorkflowModel, description: str, registered_skills, available_context) -> dict
内部流程变为：

WorkflowModel → ProtocolService.validate(model) + dry_run_contract_check(model) 校验
校验通过 → WorkflowSerializer.render(model) 渲染为 Markdown 文本 → 写入 dev/ 目录
写入索引

旧的 register_generated_workflow(artifact: str) 保留作为兼容入口，内部先调 Parser 解析、Normalizer 清洗，再转成 WorkflowModel 走新路径。过渡期这两条路都支持，新路径落地后逐步废弃旧路径。[待定：两条路径共存的时机和过渡期长度]

## 三、"no dirty write" 保障

现有实现：先写文件，校验失败再删文件。这个"先写后删"存在竞争窗口（写入后进程崩溃，文件残留）。
改为"先校验后写入"：WorkflowModel 在内存里完成协议层校验（Gatekeeper + DryRun），全部通过后才写文件和更新索引。这和纲领文档里的"注册顺序：Validate → DryRun → Write Index"一致。
写索引用现有的原子写法（写 .tmp 再 os.replace），保持不变，这是正确的防损坏写法。

## 四、_validate_engine_compatibility() 的变化

现有实现是 protocol_service.evaluate_workflow_file(filepath=...) 从文件路径读取再校验，因为注册时已经写了文件。重构后改为直接传 WorkflowModel 对象给 ProtocolService.validate(model)，不需要文件路径（因为还没写文件）。这是先校验后写入带来的接口变化。

## 五、其余方法

resolve_path(workflow_id) 保持不变。
validate_entry() / validate_entry_report() 保持不变，这两个方法仍然从文件路径读取（用于已注册工作流的事后检查）。
prune_invalid_generated_workflows() 保持不变。
_write_index / _read_index / _to_posix 保持不变。
_build_workflow_id() 保持，时间戳 + 名称拼接。