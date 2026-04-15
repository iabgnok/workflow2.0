# infra/state_store.py（从 engine/state_store.py 搬移）

## 一、AbstractStateStore 接口定义

定义在同文件顶部或独立的 infra/interfaces.py（倾向于独立文件，见前文分析）。接口方法签名：

async connect() -> None
async close() -> None
async save_run_state(run_id, workflow_name, status, current_step_id, context, persist_meta) -> None
async load_run_state(run_id) -> dict | None
async save_step_state(run_id, step_id, status, output, full_context, persist_meta) -> None
async load_latest_step_state(run_id, status) -> dict | None
async save_run_meta(run_id, **kwargs) -> None
async load_run_meta(run_id) -> dict | None
async load_latest_champion_by_composite(req_fp, bp_fp) -> dict | None

SQLiteStateStore（现有 StateStore）实现这个接口，所有逻辑不变，只是类名改变。StateStore = SQLiteStateStore 别名向后兼容。

## 二、_init_db 的 schema 版本记录

现有没有 schema 版本表，只通过 _ensure_run_meta_columns 做 ALTER TABLE 迁移。长期隐患是 _ensure_run_meta_columns 会随着每次新增字段变长，没有回滚能力。
重构时新增一个 schema_versions 表：CREATE TABLE IF NOT EXISTS schema_versions (version INTEGER PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)。_init_db 里写入当前 schema 版本号（当前为 2，1 是初始版本，2 是加了 run_meta 扩展字段的版本）。未来新增字段通过版本号判断是否需要 migrate，而不是逐列检查。[待定：schema 版本管理的精确实现，当前阶段只新增表，不迁移已有数据]

## 三、step_logs 表的命运

现有 _init_db 里创建了 step_logs 和 step_states 两个表，但 Runner 只用 step_states，step_logs 从未写入。重构时删除 step_logs 表的创建语句（保留已有数据库文件的兼容：不用 DROP TABLE，只是不再创建）。

## 四、sanitize_for_storage 的 Pydantic 对象处理

如 engine 分析所述，_to_json_safe 遇到 Pydantic 对象会退化为 repr(value)，存储的是对象的字符串表示而不是结构化数据。重构后在 _to_json_safe 里增加：if hasattr(value, 'model_dump'): return self._to_json_safe(value.model_dump())，让 Pydantic 对象正确序列化为 dict。