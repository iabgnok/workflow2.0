# state_store.py → 移入 infra/ 重构实现细节

## 一、文件搬移

从 agent/engine/ 移入 agent/infra/，理由：SQLite 是外部存储，属于基础设施。

## 二、新增 AbstractStateStore 接口

在同文件顶部（或 infra/interfaces.py）定义 AbstractStateStore，约定 5 个核心异步方法：connect()、close()、save_run_state()、load_run_state()、save_step_state()、load_step_state()。SQLiteStateStore（现有 StateStore）实现这个接口。
这样写测试时可以注入 InMemoryStateStore（实现同一接口），不需要真实的 SQLite 文件。[待定：接口定义在同文件还是独立的 infra/interfaces.py，倾向于独立文件避免循环 import]
类名从 StateStore 改为 SQLiteStateStore，原 StateStore 作为别名保留（StateStore = SQLiteStateStore），避免破坏现有测试。

## 三、context 分层存储逻辑保持

RUNTIME_ONLY_KEYS、META_KEY_PREFIX、CONTEXT_SCHEMA_VERSION、split_context_layers()、build_context_storage_payload()、unpack_context_storage_payload() 全部保持不变，这套分层逻辑是 V4 已经完善的设计，不需要改动。
_mask_secrets()、_to_json_safe()、_safe_json_dumps()、_safe_json_loads() 保持不变。

## 四、_ensure_run_meta_columns() 的演进

现有实现用 PRAGMA table_info + ALTER TABLE ADD COLUMN 做动态迁移，这是为了兼容旧版 DB 文件在新版代码下能运行。这个机制保留，但重构后如果 run_meta 表需要新增字段，都通过这个方法添加，不改 CREATE TABLE 语句。
长远来看，应该引入 schema version 表做正式的数据库迁移。但这超出当前重构范围，[待定：是否引入 Alembic 或手写迁移脚本，当前保持现有 PRAGMA 方式]

## 五、save_run_meta() 的 COALESCE 语义

现有实现使用 COALESCE(excluded.field, run_meta.field) 做"仅更新非 NULL 字段"的 upsert。这个行为意味着一次只能更新部分字段，不会覆盖其他字段的现有值。这个语义保留，是正确的局部更新设计——ChampionTracker 可以分多次调用 save_run_meta，每次只更新自己关心的字段。

## 六、load_latest_champion_by_composite() 的归属

这个方法是为 ChampionTracker 的 composite fingerprint 匹配专门设计的，业务语义很强。保留在 SQLiteStateStore 里，因为它本质上是一个 SQL 查询，适合放在存储层。ChampionTracker 通过 state_store 接口调用它，不直接感知 SQL 细节。