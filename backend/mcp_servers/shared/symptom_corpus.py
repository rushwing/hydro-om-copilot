"""
预定义中文现象语料模板，对齐知识库 topic 键。
占位符使用 Python str.format_map() 格式，MCP Server 用实际读数填充后返回前端。
"""

VIBRATION_CORPUS: dict[str, str] = {
    "water_guide_runout_alarm": (
        "水导摆度升高至 {value:.2f} mm（报警值 {alarm:.2f} mm），"
        "1倍转频成分显著，怀疑转轮质量不平衡或导叶开度偏差"
    ),
    "top_cover_vib_alarm": (
        "顶盖振动烈度异常至 {value:.1f} mm/s，伴随低频分量（约 0.3 倍转频），"
        "可能为尾水涡带共振"
    ),
    "compound_vibration": (
        "机组振动摆度多点超标：水导摆度 {vib1:.2f} mm、"
        "上导摆度 {vib2:.2f} mm、顶盖振动 {vib3:.1f} mm/s，"
        "建议立即检查动平衡及过机流量"
    ),
}

GOVERNOR_CORPUS: dict[str, str] = {
    "pressure_low_warn": (
        "调速器压油罐压力下降至 {value:.2f} MPa"
        "（正常值 {normal:.1f} MPa），备用油泵已自动投入，"
        "需检查主泵工况及管路密封性"
    ),
    "pressure_critical": (
        "调速器压油罐压力持续下降至 {value:.2f} MPa，"
        "接近事故低油压保护值（{trip:.2f} MPa），建议立即停机检查"
    ),
    "pump_frequent_start": (
        "主油泵频繁启停，当前压力 {value:.2f} MPa，"
        "疑似调速器漏油或卸压阀故障，需开展油路巡视"
    ),
}

BEARING_CORPUS: dict[str, str] = {
    "bearing_temp_warn": (
        "{bearing_name}温度升高至 {value:.1f}℃（报警值 {alarm:.0f}℃），"
        "冷却水进出水温差 {delta_t:.1f}℃，需检查冷却水流量及换热器状况"
    ),
    "bearing_temp_critical": (
        "{bearing_name}温度已达 {value:.1f}℃（跳机值 {trip:.0f}℃），"
        "须立即停机检查，防止烧瓦"
    ),
    "cooling_water_fouling": (
        "冷却水进出水温差异常下降至 {delta_t:.1f}℃（正常值 2-5℃），"
        "疑似冷却器堵塞或结垢，散热效率下降"
    ),
}
