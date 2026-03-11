"""
Unit tests for DiagnosisStore (ring buffer).

契约：
1. push/list_all 基本 CRUD
2. 超出 max_size 时自动丢弃最旧记录（环形缓冲）
3. list_all 返回最新在前
4. get_store() 返回同一单例
5. fault_queue_max 配置控制容量
"""

from datetime import UTC, datetime

from app.store.diagnosis_store import AutoDiagnosisRecord, DiagnosisStore


def _record(unit_id: str = "#1机", session_id: str | None = None) -> AutoDiagnosisRecord:
    return AutoDiagnosisRecord(
        session_id=session_id or f"auto-{unit_id}",
        unit_id=unit_id,
        fault_types=["vibration_swing"],
        symptom_text="水导摆度升高至 0.52 mm",
        triggered_at=datetime.now(tz=UTC),
    )


class TestDiagnosisStore:
    def test_empty_store_returns_empty_list(self):
        store = DiagnosisStore(max_size=5)
        assert store.list_all() == []
        assert len(store) == 0

    def test_push_and_list(self):
        store = DiagnosisStore(max_size=5)
        r = _record("#1机")
        store.push(r)
        result = store.list_all()
        assert len(result) == 1
        assert result[0].unit_id == "#1机"

    def test_list_all_newest_first(self):
        store = DiagnosisStore(max_size=5)
        for uid in ["#1机", "#2机", "#3机"]:
            store.push(_record(uid))
        result = store.list_all()
        assert [r.unit_id for r in result] == ["#3机", "#2机", "#1机"]

    def test_ring_buffer_drops_oldest(self):
        store = DiagnosisStore(max_size=3)
        for i in range(1, 6):
            store.push(_record(f"#{i}机", session_id=f"s{i}"))
        assert len(store) == 3
        ids = [r.unit_id for r in store.list_all()]
        assert "#1机" not in ids and "#2机" not in ids
        assert "#5机" in ids

    def test_max_size_one(self):
        store = DiagnosisStore(max_size=1)
        store.push(_record("#1机"))
        store.push(_record("#2机"))
        assert len(store) == 1
        assert store.list_all()[0].unit_id == "#2机"

    def test_len_tracks_count(self):
        store = DiagnosisStore(max_size=5)
        for i in range(3):
            store.push(_record(f"#{i+1}机"))
        assert len(store) == 3

    def test_record_fields_preserved(self):
        store = DiagnosisStore(max_size=5)
        r = AutoDiagnosisRecord(
            session_id="s123",
            unit_id="#2机",
            fault_types=["governor_oil_pressure"],
            symptom_text="油压下降至 4.5 MPa",
            risk_level="high",
            escalation_required=True,
            root_causes=[{"rank": 1, "title": "漏油"}],
            error=None,
        )
        store.push(r)
        result = store.list_all()[0]
        assert result.session_id == "s123"
        assert result.risk_level == "high"
        assert result.escalation_required is True
        assert result.root_causes[0]["title"] == "漏油"


class TestGetStore:
    def test_singleton_returns_same_instance(self):
        from app.store.diagnosis_store import get_store
        s1 = get_store()
        s2 = get_store()
        assert s1 is s2

    def test_singleton_uses_fault_queue_max(self):
        from app.config import settings
        from app.store.diagnosis_store import get_store
        store = get_store()
        # max_size should match config
        assert store._queue.maxlen == settings.fault_queue_max
