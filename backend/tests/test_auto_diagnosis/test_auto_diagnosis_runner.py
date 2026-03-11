"""
Unit tests for auto_diagnosis runner.

契约：
1. run_auto_diagnosis() 将 FaultSummary.symptom_text → raw_query 传入 graph
2. graph.ainvoke 成功时 record 写入 store，字段正确映射
3. graph.ainvoke 抛异常时 record 仍写入 store（error 字段非 None）
4. 每次调用生成唯一 session_id（"auto-" 前缀）
5. 路由端点 GET /diagnosis/auto-results 返回 store 内容
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.agents.auto_diagnosis import run_auto_diagnosis
from app.store.diagnosis_store import AutoDiagnosisRecord, DiagnosisStore
from mcp_servers.fault_aggregator import FaultSummary


def _make_summary(unit_id: str = "#1机") -> FaultSummary:
    return FaultSummary(
        unit_id=unit_id,
        fault_types=["vibration_swing"],
        anomaly_points=[],
        symptom_text="水导摆度升高至 0.52 mm（报警值 0.45 mm），1倍转频成分显著",
        sensor_reports=[],
    )


def _make_final_state(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "raw_query": "水导摆度升高至 0.52 mm",
        "root_causes": [{"rank": 1, "title": "转轮质量不平衡", "probability": 0.65}],
        "check_steps": [{"step": 1, "action": "检查导叶开度"}],
        "risk_level": "high",
        "escalation_required": True,
        "escalation_reason": "摆度超过报警值",
        "report_draft": "本次诊断结论...",
        "sources": ["VIB.001"],
        "error": None,
    }


# ─── runner unit tests ────────────────────────────────────────────────────────

class TestRunAutoDiagnosis:
    @pytest.mark.asyncio
    async def test_success_writes_record_to_store(self):
        store = DiagnosisStore(max_size=5)
        summary = _make_summary()

        captured_state: dict = {}

        async def mock_ainvoke(state, **kwargs):
            captured_state.update(state)
            return _make_final_state(state["session_id"])

        with patch("app.agents.auto_diagnosis.get_compiled_graph") as mock_graph_fn:
            mock_graph_fn.return_value.ainvoke = mock_ainvoke
            record = await run_auto_diagnosis(summary, store)

        assert len(store) == 1
        assert record is store.list_all()[0]

    @pytest.mark.asyncio
    async def test_raw_query_is_symptom_text(self):
        store = DiagnosisStore(max_size=5)
        summary = _make_summary()

        captured_state: dict = {}

        async def mock_ainvoke(state, **kwargs):
            captured_state.update(state)
            return _make_final_state(state["session_id"])

        with patch("app.agents.auto_diagnosis.get_compiled_graph") as mock_graph_fn:
            mock_graph_fn.return_value.ainvoke = mock_ainvoke
            await run_auto_diagnosis(summary, store)

        assert captured_state["raw_query"] == summary.symptom_text

    @pytest.mark.asyncio
    async def test_session_id_has_auto_prefix(self):
        store = DiagnosisStore(max_size=5)
        summary = _make_summary()

        async def mock_ainvoke(state, **kwargs):
            return _make_final_state(state["session_id"])

        with patch("app.agents.auto_diagnosis.get_compiled_graph") as mock_graph_fn:
            mock_graph_fn.return_value.ainvoke = mock_ainvoke
            record = await run_auto_diagnosis(summary, store)

        assert record.session_id.startswith("auto-")

    @pytest.mark.asyncio
    async def test_unique_session_ids_per_call(self):
        store = DiagnosisStore(max_size=5)
        summary = _make_summary()

        async def mock_ainvoke(state, **kwargs):
            return _make_final_state(state["session_id"])

        with patch("app.agents.auto_diagnosis.get_compiled_graph") as mock_graph_fn:
            mock_graph_fn.return_value.ainvoke = mock_ainvoke
            r1 = await run_auto_diagnosis(summary, store)
            r2 = await run_auto_diagnosis(summary, store)

        assert r1.session_id != r2.session_id

    @pytest.mark.asyncio
    async def test_state_fields_mapped_to_record(self):
        store = DiagnosisStore(max_size=5)
        summary = _make_summary("#2机")

        async def mock_ainvoke(state, **kwargs):
            return _make_final_state(state["session_id"])

        with patch("app.agents.auto_diagnosis.get_compiled_graph") as mock_graph_fn:
            mock_graph_fn.return_value.ainvoke = mock_ainvoke
            record = await run_auto_diagnosis(summary, store)

        assert record.unit_id == "#2机"
        assert record.fault_types == ["vibration_swing"]
        assert record.risk_level == "high"
        assert record.escalation_required is True
        assert record.escalation_reason == "摆度超过报警值"
        assert len(record.root_causes) == 1
        assert record.error is None

    @pytest.mark.asyncio
    async def test_graph_exception_still_writes_record(self):
        """graph.ainvoke 抛异常时 record 写入 store，error 字段非 None。"""
        store = DiagnosisStore(max_size=5)
        summary = _make_summary()

        async def failing_ainvoke(state, **kwargs):
            raise RuntimeError("LLM API unavailable")

        with patch("app.agents.auto_diagnosis.get_compiled_graph") as mock_graph_fn:
            mock_graph_fn.return_value.ainvoke = failing_ainvoke
            record = await run_auto_diagnosis(summary, store)

        assert len(store) == 1
        assert record.error is not None
        assert "LLM API unavailable" in record.error
        assert record.root_causes == []  # no LLM output on error

    @pytest.mark.asyncio
    async def test_initial_state_has_no_image(self):
        """自动诊断不携带图片（image_base64 = None）。"""
        store = DiagnosisStore(max_size=5)
        summary = _make_summary()
        captured: dict = {}

        async def mock_ainvoke(state, **kwargs):
            captured.update(state)
            return _make_final_state(state["session_id"])

        with patch("app.agents.auto_diagnosis.get_compiled_graph") as mock_graph_fn:
            mock_graph_fn.return_value.ainvoke = mock_ainvoke
            await run_auto_diagnosis(summary, store)

        assert captured["image_base64"] is None
        assert captured["topic"] is None  # topic 由 symptom_parser 推断，不预填


# ─── API 端点集成测试 ─────────────────────────────────────────────────────────

class TestAutoResultsEndpoint:
    def _client_with_store(self, store: DiagnosisStore):
        """构建 TestClient，并将 store 注入依赖。"""
        from app.api.deps import get_store
        from app.main import app
        app.dependency_overrides[get_store] = lambda: store
        client = TestClient(app, raise_server_exceptions=False)
        yield client
        app.dependency_overrides.clear()

    def test_empty_store_returns_empty_list(self):
        from app.api.deps import get_store
        from app.main import app
        store = DiagnosisStore(max_size=5)
        app.dependency_overrides[get_store] = lambda: store
        try:
            client = TestClient(app)
            resp = client.get("/diagnosis/auto-results")
            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            app.dependency_overrides.clear()

    def test_returns_records_newest_first(self):
        from app.api.deps import get_store
        from app.main import app
        store = DiagnosisStore(max_size=5)
        for uid in ["#1机", "#2机"]:
            store.push(AutoDiagnosisRecord(
                session_id=f"s-{uid}",
                unit_id=uid,
                fault_types=["vibration_swing"],
                symptom_text="test",
            ))
        app.dependency_overrides[get_store] = lambda: store
        try:
            client = TestClient(app)
            resp = client.get("/diagnosis/auto-results")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 2
            assert data[0]["unit_id"] == "#2机"  # newest first
            assert data[1]["unit_id"] == "#1机"
        finally:
            app.dependency_overrides.clear()

    def test_record_schema_fields_present(self):
        from app.api.deps import get_store
        from app.main import app
        store = DiagnosisStore(max_size=5)
        store.push(AutoDiagnosisRecord(
            session_id="s-test",
            unit_id="#1机",
            fault_types=["governor_oil_pressure"],
            symptom_text="油压下降",
            risk_level="medium",
            error=None,
        ))
        app.dependency_overrides[get_store] = lambda: store
        try:
            client = TestClient(app)
            resp = client.get("/diagnosis/auto-results")
            record = resp.json()[0]
            required = {"session_id", "unit_id", "fault_types", "symptom_text",
                        "triggered_at", "risk_level", "escalation_required",
                        "root_causes", "check_steps", "error"}
            assert required.issubset(record.keys())
        finally:
            app.dependency_overrides.clear()
