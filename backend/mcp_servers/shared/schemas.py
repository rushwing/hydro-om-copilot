from datetime import datetime
from typing import Literal

from pydantic import BaseModel

AlarmState = Literal["normal", "warn", "alarm", "trip"]
TrendDir = Literal["stable", "rising", "falling"]


class ThresholdSpec(BaseModel):
    normal_min: float
    normal_max: float
    warn: float | None = None
    alarm: float | None = None
    trip: float | None = None
    unit: str
    higher_is_worse: bool = True  # False → low-value faults (pressure, delta_t)


class SensorPoint(BaseModel):
    tag: str
    name_cn: str
    value: float
    thresholds: ThresholdSpec
    alarm_state: AlarmState
    trend: TrendDir
    timestamp: datetime


class SensorReport(BaseModel):
    sensor_id: str
    fault_type: str
    unit_id: str
    readings: list[SensorPoint]
    has_anomaly: bool
    anomaly_points: list[SensorPoint]
    epoch_num: int
    epoch_elapsed_s: int
    symptom_corpus: str | None
