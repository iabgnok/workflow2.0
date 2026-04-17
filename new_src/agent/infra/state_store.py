"""持久化状态存储层。

定义 AbstractStateStore 抽象接口（9 个 async 方法）和
SQLiteStateStore 实现。所有序列化均使用 JSON，禁止 pickle。
"""
from __future__ import annotations

import abc
import aiosqlite
import copy
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# ── 抽象接口 ──────────────────────────────────────────────────────────────────

class AbstractStateStore(abc.ABC):
    """状态存储抽象接口。

    定义引擎层所需的全部持久化契约。具体实现（SQLite、PostgreSQL 等）
    继承此类并实现所有抽象方法。
    """

    @abc.abstractmethod
    async def connect(self) -> None:
        """建立数据库连接并初始化表结构。"""

    @abc.abstractmethod
    async def close(self) -> None:
        """关闭数据库连接。"""

    @abc.abstractmethod
    async def save_run_state(
        self,
        run_id: str,
        workflow_name: str,
        status: str,
        current_step_id: int,
        context: dict,
        persist_meta: bool = False,
    ) -> None:
        """保存任务当前的运行状态。"""

    @abc.abstractmethod
    async def load_run_state(self, run_id: str) -> dict | None:
        """加载中断的任务状态。"""

    @abc.abstractmethod
    async def save_step_state(
        self,
        run_id: str,
        step_id: int,
        status: str,
        output: dict,
        full_context: dict,
        persist_meta: bool = False,
    ) -> None:
        """保存步骤执行状态快照。"""

    @abc.abstractmethod
    async def load_latest_step_state(self, run_id: str, status: str = "success") -> dict | None:
        """加载最新的指定状态步骤快照。"""

    @abc.abstractmethod
    async def save_run_meta(
        self,
        run_id: str,
        champion_json=None,
        last_feedback: str | None = None,
        requirement_fingerprint: str | None = None,
        blueprint_fingerprint: str | None = None,
        registration_audit=None,
        context_pressure=None,
    ) -> None:
        """保存运行元信息（champion、反馈、指纹等）。"""

    @abc.abstractmethod
    async def load_run_meta(self, run_id: str) -> dict | None:
        """加载运行元信息。"""

    @abc.abstractmethod
    async def load_latest_champion_by_requirement(
        self, requirement_fingerprint: str
    ) -> dict | None:
        """按需求指纹查询最新 champion。"""

    @abc.abstractmethod
    async def load_latest_champion_by_composite(
        self,
        requirement_fingerprint: str,
        blueprint_fingerprint: str,
    ) -> dict | None:
        """按需求 + 蓝图双指纹查询最新 champion。"""


# ── SQLite 实现 ───────────────────────────────────────────────────────────────

class SQLiteStateStore(AbstractStateStore):
    """基于 SQLite 的状态存储实现。

    所有数据使用 JSON 序列化落盘，禁止 pickle。
    支持多版本 context 结构的向后兼容读取。
    """

    RUNTIME_ONLY_KEYS = {"registered_skills", "chat_history"}
    META_KEY_PREFIX = "__"
    CONTEXT_SCHEMA_VERSION = "context_layers_v1"

    def __init__(self, db_path: str = "workflow_state.db"):
        self.db_path = db_path
        self._conn = None

    # ── 连接管理 ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        if not self._conn:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(self.db_path)
            await self._init_db()
            logger.info("📦 状态数据库已连接。")

    async def _init_db(self) -> None:
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                workflow_name TEXT,
                status TEXT,
                current_step_id INTEGER,
                context TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS step_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                step_id INTEGER,
                status TEXT,
                output TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
        ''')
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS step_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                step_id INTEGER,
                status TEXT,
                output TEXT,
                full_context TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(run_id, step_id),
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
        ''')
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS run_meta (
                run_id TEXT PRIMARY KEY,
                champion_json TEXT,
                last_feedback TEXT,
                requirement_fingerprint TEXT,
                registration_audit_json TEXT,
                blueprint_fingerprint TEXT,
                context_pressure_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
        ''')
        await self._ensure_run_meta_columns()
        await self._conn.commit()

    async def _ensure_run_meta_columns(self) -> None:
        async with self._conn.execute("PRAGMA table_info(run_meta)") as cursor:
            rows = await cursor.fetchall()
        existing_columns = {row[1] for row in rows}
        migrations = [
            ("requirement_fingerprint", "TEXT"),
            ("blueprint_fingerprint", "TEXT"),
            ("registration_audit_json", "TEXT"),
            ("context_pressure_json", "TEXT"),
        ]
        for col, col_type in migrations:
            if col not in existing_columns:
                await self._conn.execute(
                    f"ALTER TABLE run_meta ADD COLUMN {col} {col_type}"
                )

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("📦 状态数据库连接已关闭。")

    # ── 序列化工具（JSON-only，禁止 pickle）──────────────────────────────────

    def _mask_secrets(self, context: dict) -> dict:
        """启发式脱敏，避免 API 密钥等凭据明文落库。"""
        safe_context = copy.deepcopy(context)
        sensitive_keywords = {'api_key', 'token', 'secret', 'password', 'credential', 'auth'}
        for k, v in safe_context.items():
            if any(sec in k.lower() for sec in sensitive_keywords) and isinstance(v, str):
                safe_context[k] = "******"
            elif isinstance(v, dict):
                safe_context[k] = self._mask_secrets(v)
        return safe_context

    def _to_json_safe(self, value) -> object:
        """将任意对象转换为 JSON-safe 结构。禁止使用 pickle。"""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(k): self._to_json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._to_json_safe(v) for v in value]
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return repr(value)

    def _strip_runtime_fields(self, payload):
        if not isinstance(payload, dict):
            return payload
        return {k: v for k, v in payload.items() if k not in self.RUNTIME_ONLY_KEYS}

    def context_field_tier(self, key: str) -> str:
        """字段分层约定：runtime / meta / state。"""
        text = str(key or "")
        if text in self.RUNTIME_ONLY_KEYS:
            return "runtime"
        if text.startswith(self.META_KEY_PREFIX):
            return "meta"
        return "state"

    def sanitize_for_storage(self, context, drop_runtime: bool = False):
        """落盘前统一做脱敏与 JSON-safe 归一化。"""
        if isinstance(context, dict):
            masked = self._mask_secrets(context)
            if drop_runtime:
                masked = self._strip_runtime_fields(masked)
            normalized = self._to_json_safe(masked)
            return normalized if isinstance(normalized, dict) else {"value": normalized}
        return {"value": self._to_json_safe(context)}

    def split_context_layers(self, context: dict) -> tuple[dict, dict, dict]:
        """按字段分层拆分 context：state / meta / runtime。"""
        if not isinstance(context, dict):
            return {}, {}, {}
        state: dict = {}
        meta: dict = {}
        runtime: dict = {}
        for key, value in context.items():
            tier = self.context_field_tier(key)
            if tier == "runtime":
                runtime[key] = value
            elif tier == "meta":
                meta[key] = value
            else:
                state[key] = value
        return state, meta, runtime

    def build_context_storage_payload(self, context: dict, persist_meta: bool = False) -> dict:
        """构建分层落盘结构，默认仅持久化 state。"""
        normalized = self.sanitize_for_storage(context)
        state, meta, _ = self.split_context_layers(normalized)
        payload: dict = {"schema": self.CONTEXT_SCHEMA_VERSION, "state": state}
        if persist_meta and meta:
            payload["meta"] = meta
        return payload

    def unpack_context_storage_payload(self, payload: dict) -> tuple[dict, dict]:
        """解析分层落盘结构，返回 (state, meta)。兼容旧数据格式。"""
        if not isinstance(payload, dict):
            return {}, {}
        if payload.get("schema") == self.CONTEXT_SCHEMA_VERSION:
            state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
            meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
            return state, meta
        legacy_state, legacy_meta, _ = self.split_context_layers(payload)
        return legacy_state, legacy_meta

    def _safe_json_dumps(self, payload) -> str:
        try:
            return json.dumps(payload, ensure_ascii=False)
        except TypeError as e:
            logger.error("❌ Context 包含无法 JSON 序列化的对象: %s", e)
            return json.dumps(self._to_json_safe(payload), ensure_ascii=False)

    def _safe_json_loads(self, raw: str) -> dict:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    # ── 运行状态 ─────────────────────────────────────────────────────────────

    async def save_run_state(
        self,
        run_id: str,
        workflow_name: str,
        status: str,
        current_step_id: int,
        context: dict,
        persist_meta: bool = False,
    ) -> None:
        storage_payload = self.build_context_storage_payload(context or {}, persist_meta=persist_meta)
        context_str = self._safe_json_dumps(storage_payload)
        try:
            await self._conn.execute(
                '''
                INSERT INTO runs (run_id, workflow_name, status, current_step_id, context)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status=excluded.status,
                    current_step_id=excluded.current_step_id,
                    context=excluded.context,
                    updated_at=CURRENT_TIMESTAMP
                ''',
                (run_id, workflow_name, status, current_step_id, context_str),
            )
            await self._conn.commit()
        except aiosqlite.OperationalError as e:
            logger.error("❌ 数据库并发操作失败: %s", e)
            raise Exception(f"Failed to write state into database: {e}")

    async def load_run_state(self, run_id: str) -> dict | None:
        async with self._conn.execute(
            'SELECT workflow_name, status, current_step_id, context FROM runs WHERE run_id = ?',
            (run_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                raw_context = self._safe_json_loads(row[3])
                state_context, meta_context = self.unpack_context_storage_payload(raw_context)
                return {
                    "workflow_name": row[0],
                    "status": row[1],
                    "current_step_id": row[2],
                    "context": state_context,
                    "meta_context": meta_context,
                }
            return None

    # ── 步骤状态 ─────────────────────────────────────────────────────────────

    async def save_step_state(
        self,
        run_id: str,
        step_id: int,
        status: str,
        output: dict,
        full_context: dict,
        persist_meta: bool = False,
    ) -> None:
        safe_output = self.sanitize_for_storage(output or {})
        safe_context = self.build_context_storage_payload(full_context or {}, persist_meta=persist_meta)
        output_str = self._safe_json_dumps(safe_output)
        context_str = self._safe_json_dumps(safe_context)
        await self._conn.execute(
            '''
            INSERT INTO step_states (run_id, step_id, status, output, full_context)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id, step_id) DO UPDATE SET
                status=excluded.status,
                output=excluded.output,
                full_context=excluded.full_context,
                updated_at=CURRENT_TIMESTAMP
            ''',
            (run_id, step_id, status, output_str, context_str),
        )
        await self._conn.commit()

    async def load_latest_step_state(self, run_id: str, status: str = "success") -> dict | None:
        async with self._conn.execute(
            '''
            SELECT step_id, status, output, full_context
            FROM step_states
            WHERE run_id = ? AND status = ?
            ORDER BY step_id DESC
            LIMIT 1
            ''',
            (run_id, status),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            raw_context = self._safe_json_loads(row[3])
            state_context, meta_context = self.unpack_context_storage_payload(raw_context)
            return {
                "step_id": row[0],
                "status": row[1],
                "output": self._safe_json_loads(row[2]),
                "full_context": state_context,
                "meta_full_context": meta_context,
            }

    # ── 运行元信息 ────────────────────────────────────────────────────────────

    async def save_run_meta(
        self,
        run_id: str,
        champion_json=None,
        last_feedback: str | None = None,
        requirement_fingerprint: str | None = None,
        blueprint_fingerprint: str | None = None,
        registration_audit=None,
        context_pressure=None,
    ) -> None:
        def _encode(obj):
            if obj is None:
                return None
            safe = self.sanitize_for_storage(obj if isinstance(obj, dict) else {"value": obj})
            return self._safe_json_dumps(safe)

        await self._conn.execute(
            '''
            INSERT INTO run_meta (
                run_id, champion_json, last_feedback,
                requirement_fingerprint, blueprint_fingerprint,
                registration_audit_json, context_pressure_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                champion_json=COALESCE(excluded.champion_json, run_meta.champion_json),
                last_feedback=COALESCE(excluded.last_feedback, run_meta.last_feedback),
                requirement_fingerprint=COALESCE(excluded.requirement_fingerprint, run_meta.requirement_fingerprint),
                blueprint_fingerprint=COALESCE(excluded.blueprint_fingerprint, run_meta.blueprint_fingerprint),
                registration_audit_json=COALESCE(excluded.registration_audit_json, run_meta.registration_audit_json),
                context_pressure_json=COALESCE(excluded.context_pressure_json, run_meta.context_pressure_json),
                updated_at=CURRENT_TIMESTAMP
            ''',
            (
                run_id,
                _encode(champion_json),
                last_feedback,
                requirement_fingerprint,
                blueprint_fingerprint,
                _encode(registration_audit),
                _encode(context_pressure),
            ),
        )
        await self._conn.commit()

    async def load_run_meta(self, run_id: str) -> dict | None:
        async with self._conn.execute(
            'SELECT champion_json, last_feedback, registration_audit_json, context_pressure_json '
            'FROM run_meta WHERE run_id = ?',
            (run_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "champion_json": self._safe_json_loads(row[0]) if row[0] else None,
                "last_feedback": row[1],
                "registration_audit": self._safe_json_loads(row[2]) if row[2] else None,
                "context_pressure": self._safe_json_loads(row[3]) if row[3] else None,
            }

    # ── Champion 查询 ──────────────────────────────────────────────────────────

    async def load_latest_champion_by_requirement(
        self, requirement_fingerprint: str
    ) -> dict | None:
        async with self._conn.execute(
            '''
            SELECT champion_json, last_feedback
            FROM run_meta
            WHERE requirement_fingerprint = ? AND champion_json IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT 1
            ''',
            (requirement_fingerprint,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "champion_json": self._safe_json_loads(row[0]) if row[0] else None,
                "last_feedback": row[1],
            }

    async def load_latest_champion_by_composite(
        self,
        requirement_fingerprint: str,
        blueprint_fingerprint: str,
    ) -> dict | None:
        async with self._conn.execute(
            '''
            SELECT champion_json, last_feedback
            FROM run_meta
            WHERE requirement_fingerprint = ?
              AND blueprint_fingerprint = ?
              AND champion_json IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT 1
            ''',
            (requirement_fingerprint, blueprint_fingerprint),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "champion_json": self._safe_json_loads(row[0]) if row[0] else None,
                "last_feedback": row[1],
            }
