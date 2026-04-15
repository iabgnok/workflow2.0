# workflows/registry/index.json（新位置）

## 一、从 workflows/index.json 迁移

现有 index.json 在 workflows/ 根目录，和 meta/、dev/ 目录平级。重构后移到 workflows/registry/index.json，独立存放，原因在纲领文档里已说明：索引和内容文件生命周期解耦。
WorkflowRegistry 的 index_path 默认值从 settings.py 读取，指向新路径 workflows/registry/index.json。

## 二、索引文件格式本身不变

保持现有 JSON 格式：{workflow_id: {path, description, version, created_at}}，每个条目的结构不变。
meta_main_workflow 这个内置索引条目保留，但 path 字段的值调整为相对路径（相对于项目根目录），和现有一致。
新增 schema_version 字段（[待定]）：顶层加 "schema_version": 1，为将来索引格式升级预留版本判断入口。[待定：是否需要这个字段，当前格式足够简单，版本控制意义不大]