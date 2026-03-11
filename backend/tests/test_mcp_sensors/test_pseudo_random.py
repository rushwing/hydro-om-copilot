"""
Unit tests for shared/pseudo_random.py

契约：
1. unit_tag() — "#N机" → "UN" 映射正确，边界安全
2. 稳定种子 — 相同 sensor_id + epoch 在不同 PYTHONHASHSEED 下值不变
3. _alarm_state() — higher_is_worse / lower 两个分支均正确
4. Epoch 内同参数多次调用平滑（值变化幅度不超过基值 20%）
5. is_fault_epoch / affected_params 在同一 epoch 内确定
"""

import subprocess
import sys
from unittest.mock import patch

from mcp_servers.shared.pseudo_random import (
    PseudoRandomEngine,
    _alarm_state,
    unit_tag,
)
from mcp_servers.shared.schemas import ThresholdSpec

# ─── unit_tag ────────────────────────────────────────────────────────────────

class TestUnitTag:
    def test_single_digit(self):
        assert unit_tag("#1机") == "U1"

    def test_multi_digit(self):
        assert unit_tag("#12机") == "U12"

    def test_all_standard_units(self):
        expected = {"#1机": "U1", "#2机": "U2", "#3机": "U3", "#4机": "U4"}
        for uid, tag in expected.items():
            assert unit_tag(uid) == tag

    def test_no_digit_falls_back(self):
        """无数字时返回原值，不抛异常。"""
        result = unit_tag("机组A")
        assert result == "机组A"

    def test_leading_zeros(self):
        assert unit_tag("#01机") == "U01"


# ─── _alarm_state ─────────────────────────────────────────────────────────────

class TestAlarmState:
    def _spec(self, warn=None, alarm=None, trip=None, higher=True):
        return ThresholdSpec(
            normal_min=0.0,
            normal_max=10.0,
            warn=warn,
            alarm=alarm,
            trip=trip,
            unit="mm",
            higher_is_worse=higher,
        )

    # higher_is_worse=True
    def test_normal_below_warn(self):
        spec = self._spec(warn=5.0, alarm=8.0, trip=10.0)
        assert _alarm_state(3.0, spec) == "normal"

    def test_warn_level(self):
        spec = self._spec(warn=5.0, alarm=8.0, trip=10.0)
        assert _alarm_state(5.5, spec) == "warn"

    def test_alarm_level(self):
        spec = self._spec(warn=5.0, alarm=8.0, trip=10.0)
        assert _alarm_state(8.5, spec) == "alarm"

    def test_trip_level(self):
        spec = self._spec(warn=5.0, alarm=8.0, trip=10.0)
        assert _alarm_state(10.0, spec) == "trip"

    def test_trip_boundary_exact(self):
        spec = self._spec(trip=10.0)
        assert _alarm_state(10.0, spec) == "trip"

    # higher_is_worse=False (low-value faults: pressure, delta_t)
    def test_low_value_normal(self):
        spec = self._spec(warn=5.0, trip=2.0, higher=False)
        assert _alarm_state(7.0, spec) == "normal"

    def test_low_value_warn(self):
        spec = self._spec(warn=5.0, trip=2.0, higher=False)
        assert _alarm_state(4.0, spec) == "warn"

    def test_low_value_trip(self):
        spec = self._spec(trip=2.0, higher=False)
        assert _alarm_state(1.5, spec) == "trip"

    def test_low_value_trip_boundary(self):
        spec = self._spec(trip=2.0, higher=False)
        assert _alarm_state(2.0, spec) == "trip"

    def test_no_thresholds_always_normal(self):
        spec = self._spec()
        assert _alarm_state(999.0, spec) == "normal"


# ─── 稳定种子 (P2) ───────────────────────────────────────────────────────────

class TestStableSeed:
    """
    跨 PYTHONHASHSEED 一致性：spawn 子进程设置不同 PYTHONHASHSEED，
    确认 _stable_seed() 和 seeded RNG 首个输出值不受影响。

    注意：compute_value() 含 math.sin(elapsed * 0.1) 项，使用真实 time.time()，
    因此跨进程的完整值会因时间不同而漂移；此处只测种子本身的确定性。
    """

    def _get_seed_in_subprocess(self, hashseed: int) -> str:
        """在子进程中获取 _stable_seed 输出（SHA-256，不受 PYTHONHASHSEED 影响）。"""
        code = (
            "from mcp_servers.shared.pseudo_random import PseudoRandomEngine;"
            "e = PseudoRandomEngine('test:vibration:#1机');"
            "print(e._stable_seed('test:vibration:#1机:1234:0'))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env={"PYTHONHASHSEED": str(hashseed), "PYTHONPATH": "."},
            cwd=str(__import__("pathlib").Path(__file__).parent.parent.parent),
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    def _get_rng_first_value_in_subprocess(self, hashseed: int) -> str:
        """在子进程中获取同 epoch/salt RNG 的首个 random() 值。"""
        import os
        import tempfile
        import textwrap

        script = textwrap.dedent("""\
            from unittest.mock import patch
            from mcp_servers.shared.pseudo_random import PseudoRandomEngine
            e = PseudoRandomEngine('test:vibration:#1机')
            with patch.object(type(e), '_epoch_num', return_value=999999):
                print(round(e._rng(0).random(), 8))
        """)
        backend_dir = str(__import__("pathlib").Path(__file__).parent.parent.parent)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script)
            tmp = f.name
        try:
            result = subprocess.run(
                [sys.executable, tmp],
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONHASHSEED": str(hashseed), "PYTHONPATH": backend_dir},
                cwd=backend_dir,
            )
        finally:
            os.unlink(tmp)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    def test_stable_seed_identical_across_hashseeds(self):
        """SHA-256 种子在不同 PYTHONHASHSEED 下产出相同整数。"""
        s1 = self._get_seed_in_subprocess(42)
        s2 = self._get_seed_in_subprocess(12345)
        s3 = self._get_seed_in_subprocess(99999)
        assert s1 == s2 == s3, (
            f"_stable_seed differs across PYTHONHASHSEED: {s1!r}, {s2!r}, {s3!r}"
        )

    def test_rng_first_value_identical_across_hashseeds(self):
        """固定 epoch 下 _rng() 首个随机值跨进程不变。"""
        v1 = self._get_rng_first_value_in_subprocess(42)
        v2 = self._get_rng_first_value_in_subprocess(12345)
        v3 = self._get_rng_first_value_in_subprocess(99999)
        assert v1 == v2 == v3, (
            f"RNG first value differs across PYTHONHASHSEED: {v1!r}, {v2!r}, {v3!r}"
        )


# ─── Epoch 一致性 ─────────────────────────────────────────────────────────────

class TestEpochConsistency:
    """同一 epoch 内，is_fault_epoch 和 affected_params 必须稳定。"""

    def test_fault_epoch_stable_within_epoch(self):
        engine = PseudoRandomEngine("vibration:#1机")
        results = [engine.is_fault_epoch() for _ in range(10)]
        assert len(set(results)) == 1, "is_fault_epoch changed within epoch"

    def test_affected_params_stable_within_epoch(self):
        tags = ["A", "B", "C", "D", "E"]
        engine = PseudoRandomEngine("vibration:#1机")
        first = engine.affected_params(tags)
        for _ in range(9):
            assert engine.affected_params(tags) == first

    def test_affected_params_count_between_2_and_3(self):
        tags = ["A", "B", "C", "D", "E"]
        engine = PseudoRandomEngine("vibration:#1机")
        count = len(engine.affected_params(tags))
        assert 2 <= count <= 3

    def test_different_sensor_ids_independent(self):
        """不同 sensor_id 的 engine 故障状态相互独立。"""
        tags = ["X", "Y", "Z", "W", "V"]
        e1 = PseudoRandomEngine("vibration:#1机")
        e2 = PseudoRandomEngine("governor:#1机")
        # 可能相同也可能不同，但不能断言二者必须相等
        # 只要各自调用多次保持内部稳定
        assert e1.affected_params(tags) == e1.affected_params(tags)
        assert e2.affected_params(tags) == e2.affected_params(tags)

    def test_value_smoothness_within_epoch(self):
        """同一 epoch 内相邻 15s 窗口的值变化不超过基值 20%。"""
        engine = PseudoRandomEngine("vibration:#1机")
        base = 0.12
        affected: list[str] = []  # normal epoch

        # 模拟 0s、15s、30s 三个窗口
        values = []
        for elapsed in (0, 15, 30):
            with patch.object(type(engine), "_elapsed", return_value=elapsed):
                v = engine.compute_value("WATER_GUIDE_RUNOUT", base, 0.52, 0.02, affected)
                values.append(v)

        for i in range(len(values) - 1):
            delta = abs(values[i + 1] - values[i])
            assert delta < base * 0.20, (
                f"Value jumped {delta:.4f} between windows {i} and {i+1}: {values}"
            )
