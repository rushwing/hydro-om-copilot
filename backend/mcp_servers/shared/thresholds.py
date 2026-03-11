"""
门限常量 — 源自知识库 L2.SUPPORT.RULE.001 / RB_TOPIC.VIB / RB_P_001/002/005
参考机组：150MW 级立轴混流式水轮发电机组
"""

from dataclasses import dataclass

from .schemas import ThresholdSpec


@dataclass
class TagSpec:
    tag: str
    name_cn: str
    thresholds: ThresholdSpec
    base_val: float       # 正常运行中心值（伪随机引擎基准）
    fault_target: float   # 故障充分发展时目标值
    noise_pct: float = 0.02  # 正常噪声占 base_val 的比例


# ─────────────────────── 振动摆度 ───────────────────────
# 来源：L2.TOPIC.VIB.001 + RB_TOPIC.VIB（案例：水导摆度报警 0.45mm）

VIBRATION_THRESHOLDS: list[TagSpec] = [
    TagSpec(
        tag="WATER_GUIDE_RUNOUT",
        name_cn="水导摆度",
        thresholds=ThresholdSpec(
            normal_min=0.0,
            normal_max=0.20,
            warn=0.30,
            alarm=0.45,
            trip=0.60,
            unit="mm",
            higher_is_worse=True,
        ),
        base_val=0.12,
        fault_target=0.52,
    ),
    TagSpec(
        tag="UPPER_GUIDE_RUNOUT",
        name_cn="上导摆度",
        thresholds=ThresholdSpec(
            normal_min=0.0,
            normal_max=0.15,
            warn=0.22,
            alarm=0.30,
            trip=0.40,
            unit="mm",
            higher_is_worse=True,
        ),
        base_val=0.09,
        fault_target=0.36,
    ),
    TagSpec(
        tag="TOP_COVER_VIB",
        name_cn="顶盖振动烈度",
        thresholds=ThresholdSpec(
            normal_min=0.0,
            normal_max=2.8,
            warn=3.5,
            alarm=4.5,
            trip=6.0,
            unit="mm/s",
            higher_is_worse=True,
        ),
        base_val=1.8,
        fault_target=5.0,
        noise_pct=0.03,
    ),
    TagSpec(
        tag="STATOR_FRAME_VIB",
        name_cn="定子机架振动烈度",
        thresholds=ThresholdSpec(
            normal_min=0.0,
            normal_max=1.5,
            warn=2.0,
            alarm=2.5,
            trip=3.5,
            unit="mm/s",
            higher_is_worse=True,
        ),
        base_val=0.9,
        fault_target=3.0,
        noise_pct=0.03,
    ),
    TagSpec(
        tag="DOMINANT_FREQ_RATIO",
        name_cn="主频/转频比",
        thresholds=ThresholdSpec(
            normal_min=0.4,
            normal_max=1.1,
            alarm=0.4,  # 低于 0.4 为涡带区故障
            unit="x",
            higher_is_worse=False,
        ),
        base_val=0.95,
        fault_target=0.25,
        noise_pct=0.01,
    ),
]

# ─────────────────────── 调速器油压 ───────────────────────
# 来源：RB_P_005（额定 6.3 MPa；以 4.0MPa 额定按比例换算至 6.3MPa）

GOVERNOR_THRESHOLDS: list[TagSpec] = [
    TagSpec(
        tag="OIL_PRESSURE",
        name_cn="压油罐压力",
        thresholds=ThresholdSpec(
            normal_min=6.0,
            normal_max=6.3,
            warn=5.36,   # 85% of 6.3
            trip=4.41,   # 70% of 6.3
            unit="MPa",
            higher_is_worse=False,
        ),
        base_val=6.18,
        fault_target=4.2,
        noise_pct=0.005,
    ),
    TagSpec(
        tag="BACKUP_PUMP_START",
        name_cn="备用泵启动压力",
        thresholds=ThresholdSpec(
            normal_min=5.50,
            normal_max=6.30,
            warn=5.60,
            unit="MPa",
            higher_is_worse=False,
        ),
        base_val=5.90,
        fault_target=5.45,
        noise_pct=0.005,
    ),
    TagSpec(
        tag="MAIN_PUMP_START",
        name_cn="主泵启动压力",
        thresholds=ThresholdSpec(
            normal_min=5.70,
            normal_max=6.30,
            warn=5.84,
            unit="MPa",
            higher_is_worse=False,
        ),
        base_val=6.05,
        fault_target=5.65,
        noise_pct=0.005,
    ),
    TagSpec(
        tag="RELIEF_VALVE_OPEN",
        name_cn="安全阀全开压力",
        thresholds=ThresholdSpec(
            normal_min=0.0,
            normal_max=7.20,
            alarm=7.20,  # 114% of 6.3
            unit="MPa",
            higher_is_worse=True,
        ),
        base_val=6.80,
        fault_target=7.40,
        noise_pct=0.005,
    ),
    TagSpec(
        tag="OIL_TEMP",
        name_cn="油温",
        thresholds=ThresholdSpec(
            normal_min=15.0,
            normal_max=45.0,
            warn=50.0,
            alarm=55.0,
            trip=60.0,
            unit="℃",
            higher_is_worse=True,
        ),
        base_val=32.0,
        fault_target=57.0,
        noise_pct=0.02,
    ),
]

# ─────────────────────── 轴承温升冷却水 ───────────────────────
# 来源：RB_P_001, RB_P_002（案例：推力瓦 48→72℃ 烧瓦）

BEARING_THRESHOLDS: list[TagSpec] = [
    TagSpec(
        tag="UPPER_GUIDE_TEMP",
        name_cn="上导轴承温度",
        thresholds=ThresholdSpec(
            normal_min=0.0,
            normal_max=60.0,
            warn=65.0,
            trip=70.0,
            unit="℃",
            higher_is_worse=True,
        ),
        base_val=48.0,
        fault_target=72.0,
        noise_pct=0.01,
    ),
    TagSpec(
        tag="THRUST_TEMP",
        name_cn="推力轴承温度",
        thresholds=ThresholdSpec(
            normal_min=0.0,
            normal_max=55.0,
            warn=62.0,
            trip=70.0,
            unit="℃",
            higher_is_worse=True,
        ),
        base_val=43.0,
        fault_target=72.0,
        noise_pct=0.01,
    ),
    TagSpec(
        tag="WATER_GUIDE_TEMP",
        name_cn="水导轴承温度",
        thresholds=ThresholdSpec(
            normal_min=0.0,
            normal_max=60.0,
            warn=65.0,
            trip=70.0,
            unit="℃",
            higher_is_worse=True,
        ),
        base_val=47.0,
        fault_target=72.0,
        noise_pct=0.01,
    ),
    TagSpec(
        tag="BEARING_OIL_TEMP",
        name_cn="轴承油温",
        thresholds=ThresholdSpec(
            normal_min=0.0,
            normal_max=55.0,
            unit="℃",
            higher_is_worse=True,
        ),
        base_val=42.0,
        fault_target=60.0,
        noise_pct=0.01,
    ),
    TagSpec(
        tag="COOLING_WATER_TEMP",
        name_cn="冷却水温度",
        thresholds=ThresholdSpec(
            normal_min=0.0,
            normal_max=30.0,
            unit="℃",
            higher_is_worse=True,
        ),
        base_val=22.0,
        fault_target=35.0,
        noise_pct=0.02,
    ),
    TagSpec(
        tag="COOLING_WATER_PRES",
        name_cn="冷却水压力",
        thresholds=ThresholdSpec(
            normal_min=0.10,
            normal_max=0.30,
            trip=0.10,
            unit="MPa",
            higher_is_worse=False,
        ),
        base_val=0.22,
        fault_target=0.08,
        noise_pct=0.02,
    ),
    TagSpec(
        tag="DELTA_T",
        name_cn="进出水温差",
        thresholds=ThresholdSpec(
            normal_min=0.8,
            normal_max=5.0,
            trip=0.8,   # 低于 0.8℃ 疑似结垢
            unit="℃",
            higher_is_worse=False,
        ),
        base_val=3.2,
        fault_target=0.5,
        noise_pct=0.03,
    ),
]
