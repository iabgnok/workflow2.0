"""AbstractStateStore 接口测试和 SQLiteStateStore 实现测试。"""
import json
import pytest

from agent.infra.state_store import AbstractStateStore, SQLiteStateStore


# ── 接口测试 ──────────────────────────────────────────────────────────────────

class TestAbstractStateStore:
    """验证 AbstractStateStore 的 ABC 约束。"""

    def test_cannot_instantiate_abstract_class(self):
        """未实现全部抽象方法时，实例化应抛出 TypeError。"""
        with pytest.raises(TypeError):
            AbstractStateStore()

    def test_partial_implementation_raises_type_error(self):
        """只实现部分方法时，实例化仍应抛出 TypeError。"""
        class PartialStore(AbstractStateStore):
            async def connect(self): pass
            async def close(self): pass
            # 缺少其余 7 个方法

        with pytest.raises(TypeError):
            PartialStore()

    def test_full_implementation_can_be_instantiated(self):
        """完整实现所有抽象方法时，可正常实例化。"""
        class FullStore(AbstractStateStore):
            async def connect(self): pass
            async def close(self): pass
            async def save_run_state(self, *a, **kw): pass
            async def load_run_state(self, run_id): return None
            async def save_step_state(self, *a, **kw): pass
            async def load_latest_step_state(self, run_id, status="success"): return None
            async def save_run_meta(self, *a, **kw): pass
            async def load_run_meta(self, run_id): return None
            async def load_latest_champion_by_requirement(self, fp): return None
            async def load_latest_champion_by_composite(self, fp1, fp2): return None

        store = FullStore()
        assert isinstance(store, AbstractStateStore)


# ── SQLiteStateStore 序列化工具测试 ───────────────────────────────────────────

class TestSQLiteStateStoreSerialization:
    """验证 JSON-only 序列化（禁止 pickle）。"""

    def setup_method(self):
        self.store = SQLiteStateStore.__new__(SQLiteStateStore)
        self.store.db_path = ":memory:"
        self.store._conn = None

    def test_to_json_safe_primitives(self):
        assert self.store._to_json_safe(None) is None
        assert self.store._to_json_safe(42) == 42
        assert self.store._to_json_safe("hello") == "hello"
        assert self.store._to_json_safe(True) is True

    def test_to_json_safe_converts_set_to_list(self):
        result = self.store._to_json_safe({1, 2, 3})
        assert isinstance(result, list)
        assert sorted(result) == [1, 2, 3]

    def test_to_json_safe_converts_bytes(self):
        result = self.store._to_json_safe(b"hello")
        assert result == "hello"

    def test_to_json_safe_dict_recursive(self):
        data = {"key": {1, 2}, "nested": {"inner": b"val"}}
        result = self.store._to_json_safe(data)
        assert isinstance(result["key"], list)
        assert result["nested"]["inner"] == "val"

    def test_mask_secrets(self):
        context = {"api_key": "secret123", "name": "test"}
        result = self.store._mask_secrets(context)
        assert result["api_key"] == "******"
        assert result["name"] == "test"

    def test_context_field_tier(self):
        assert self.store.context_field_tier("chat_history") == "runtime"
        assert self.store.context_field_tier("registered_skills") == "runtime"
        assert self.store.context_field_tier("__meta_key") == "meta"
        assert self.store.context_field_tier("user_name") == "state"

    def test_build_and_unpack_context_storage_payload(self):
        context = {
            "user_name": "Alice",
            "__meta": "meta_value",
            "chat_history": ["msg1", "msg2"],
        }
        payload = self.store.build_context_storage_payload(context, persist_meta=True)
        assert payload["schema"] == SQLiteStateStore.CONTEXT_SCHEMA_VERSION
        assert "user_name" in payload["state"]
        assert "chat_history" not in payload["state"]  # runtime 字段被排除

        state, meta = self.store.unpack_context_storage_payload(payload)
        assert state["user_name"] == "Alice"
        assert meta.get("__meta") == "meta_value"

    def test_safe_json_dumps_and_loads(self):
        data = {"key": "value", "number": 42}
        serialized = self.store._safe_json_dumps(data)
        assert isinstance(serialized, str)
        deserialized = self.store._safe_json_loads(serialized)
        assert deserialized == data

    def test_safe_json_loads_empty_string(self):
        assert self.store._safe_json_loads("") == {}

    def test_safe_json_loads_invalid_json(self):
        assert self.store._safe_json_loads("not-json") == {}

    def test_no_pickle_in_serialization(self):
        """确认序列化结果是合法 JSON，不含 pickle 字节。"""
        context = {"data": [1, 2, 3], "nested": {"key": "value"}}
        payload = self.store.build_context_storage_payload(context)
        serialized = self.store._safe_json_dumps(payload)
        # 可被 json.loads 正常解析
        parsed = json.loads(serialized)
        assert isinstance(parsed, dict)


# ── SQLiteStateStore 完整流程测试（需要 aiosqlite）────────────────────────────

@pytest.mark.asyncio
async def test_sqlite_state_store_full_lifecycle(tmp_path):
    """测试完整的状态持久化读写流程。"""
    db_path = str(tmp_path / "test_state.db")
    store = SQLiteStateStore(db_path=db_path)

    await store.connect()
    try:
        run_id = "test-run-001"
        context = {"user_name": "Alice", "step_result": "ok", "chat_history": ["msg"]}

        # 保存运行状态
        await store.save_run_state(
            run_id=run_id,
            workflow_name="test_workflow",
            status="running",
            current_step_id=2,
            context=context,
        )

        # 加载运行状态
        loaded = await store.load_run_state(run_id)
        assert loaded is not None
        assert loaded["workflow_name"] == "test_workflow"
        assert loaded["status"] == "running"
        assert loaded["current_step_id"] == 2
        # runtime 字段（chat_history）不应出现在持久化数据中
        assert "chat_history" not in loaded["context"]
        assert loaded["context"]["user_name"] == "Alice"

        # 保存步骤状态
        await store.save_step_state(
            run_id=run_id,
            step_id=2,
            status="success",
            output={"result": "done"},
            full_context=context,
        )

        # 加载最新步骤状态
        step = await store.load_latest_step_state(run_id, status="success")
        assert step is not None
        assert step["step_id"] == 2
        assert step["output"]["result"] == "done"

        # 保存并加载元信息
        await store.save_run_meta(
            run_id=run_id,
            champion_json={"draft": "v1"},
            last_feedback="looks good",
            requirement_fingerprint="fp-req-001",
        )
        meta = await store.load_run_meta(run_id)
        assert meta is not None
        assert meta["champion_json"]["draft"] == "v1"
        assert meta["last_feedback"] == "looks good"

        # Champion 查询
        champion = await store.load_latest_champion_by_requirement("fp-req-001")
        assert champion is not None
        assert champion["champion_json"]["draft"] == "v1"

    finally:
        await store.close()
