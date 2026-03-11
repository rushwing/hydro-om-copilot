"""
伪随机引擎 — epoch 机制 + smoothstep 渐变

时间轴（每 300s 为一个 Epoch）：
  Epoch N:  |<────────────────── 300s ──────────────────>|
            0s        60s        180s       240s       300s
            ├─ NORMAL ─┤─ PRE-FAULT ─┤──── FAULT ────┤ RESET

• ~60% 概率为 Fault Epoch（epoch_rng 决定，全 epoch 内确定）
• 故障影响 2-3 个参数（epoch_rng 采样决定，全 epoch 内确定）
• t=60-120s：参数开始漂移（增加噪声，基值缓慢抬升）
• t=120-240s：smoothstep 渐进至 alarm 值（保证越线）
• t=240-300s：维持在 alarm 附近（±小幅噪声）
"""

import math
import random
import time

EPOCH_SECONDS = 300
FAULT_PROB = 0.60


def _alarm_state(value: float, spec) -> str:
    """计算 AlarmState。spec 为 ThresholdSpec 实例。"""
    if spec.higher_is_worse:
        if spec.trip is not None and value >= spec.trip:
            return "trip"
        if spec.alarm is not None and value >= spec.alarm:
            return "alarm"
        if spec.warn is not None and value >= spec.warn:
            return "warn"
    else:
        if spec.trip is not None and value <= spec.trip:
            return "trip"
        if spec.alarm is not None and value <= spec.alarm:
            return "alarm"
        if spec.warn is not None and value <= spec.warn:
            return "warn"
    return "normal"


def _trend(prev: float, curr: float) -> str:
    delta = curr - prev
    if abs(delta) < 0.001 * abs(curr + 1e-9):
        return "stable"
    return "rising" if delta > 0 else "falling"


class PseudoRandomEngine:
    def __init__(self, sensor_id: str) -> None:
        self.sensor_id = sensor_id
        self._prev_values: dict[str, float] = {}

    # ─── epoch helpers ───────────────────────────────────────────────────────

    def _epoch_num(self) -> int:
        return int(time.time() / EPOCH_SECONDS)

    def _elapsed(self) -> int:
        return int(time.time() % EPOCH_SECONDS)

    def _rng(self, salt: int = 0) -> random.Random:
        seed = hash(f"{self.sensor_id}:{self._epoch_num()}:{salt}")
        return random.Random(seed)

    # ─── epoch-level decisions (stable within epoch) ──────────────────────

    def is_fault_epoch(self) -> bool:
        return self._rng(0).random() < FAULT_PROB

    def fault_start_s(self) -> int:
        """故障漂移开始时刻（epoch 内 60~120s 随机）"""
        return self._rng(1).randint(60, 120)

    def affected_params(self, all_tags: list[str]) -> list[str]:
        """本 epoch 受影响的 2-3 个参数 tag（全 epoch 确定）"""
        rng = self._rng(2)
        n = rng.randint(2, 3)
        return rng.sample(all_tags, min(n, len(all_tags)))

    # ─── per-reading computation ──────────────────────────────────────────

    def compute_value(
        self,
        tag: str,
        base_val: float,
        fault_target: float,
        noise_pct: float,
        affected: list[str],
    ) -> float:
        """
        计算传感器当前瞬时读数。
        - 正常 epoch 或未受影响参数：Gaussian 噪声 + sin 波动
        - 故障 epoch 受影响参数：smoothstep 渐进至 fault_target
        """
        elapsed = self._elapsed()
        # 15s 分辨率的细粒度随机种子，保证短时间内值平滑
        fine_rng = random.Random(
            hash(f"{self.sensor_id}:{self._epoch_num()}:{elapsed // 15}:{tag}")
        )

        if not self.is_fault_epoch() or tag not in affected:
            noise = fine_rng.gauss(0, base_val * noise_pct)
            sin_c = math.sin(elapsed * 0.1) * base_val * noise_pct * 0.5
            return base_val + noise + sin_c

        start = self.fault_start_s()
        if elapsed < start:
            # 故障前：稍大噪声（预兆）
            noise = fine_rng.gauss(0, base_val * noise_pct * 1.5)
            return base_val + noise

        # smoothstep 渐进
        progress = min(1.0, (elapsed - start) / max(1, (EPOCH_SECONDS - start) * 0.75))
        smooth = progress * progress * (3 - 2 * progress)
        target = base_val + (fault_target - base_val) * smooth
        noise = fine_rng.gauss(0, base_val * noise_pct * 0.5)
        return target + noise

    # ─── full point computation (with trend) ─────────────────────────────

    def compute_point_value(
        self,
        tag: str,
        base_val: float,
        fault_target: float,
        noise_pct: float,
        affected: list[str],
    ) -> tuple[float, str]:
        """返回 (value, trend_dir)"""
        value = self.compute_value(tag, base_val, fault_target, noise_pct, affected)
        prev = self._prev_values.get(tag, value)
        trend = _trend(prev, value)
        self._prev_values[tag] = value
        return value, trend
