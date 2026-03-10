"""Unit tests for symptom_parser topic routing logic."""

from app.agents.symptom_parser import _infer_topic


def test_infer_topic_vibration():
    parsed = {"symptoms": ["轴振偏大", "摆度超标"], "device": "导轴承"}
    assert _infer_topic(parsed) == "vibration_swing"


def test_infer_topic_governor():
    parsed = {"symptoms": ["油压低"], "device": "主配压阀"}
    assert _infer_topic(parsed) == "governor_oil_pressure"


def test_infer_topic_bearing():
    parsed = {"symptoms": ["温升异常"], "device": "推力轴承"}
    assert _infer_topic(parsed) == "bearing_temp_cooling"
