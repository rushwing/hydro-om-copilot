# TODO — Hydro O&M Copilot

## Log System — Phase 2 (backend pipeline done ✓)

### Sensor logs (per-session)
- [ ] Write `sensor_vibration.log`, `sensor_governor.log`, `sensor_bearing.log` inside the session dir.
  - Hook into MCP sensor server read events or `sensor_reader_node` output.
  - Log each `SensorPointSnapshot` as a JSON-line: `{ts, tag, name_cn, value, alarm_state, trend}`.
  - File naming: `sensor_<fault_type_short>.log` (e.g. `sensor_vibration.log`).

### Human handling log (per-session)
- [ ] Add `POST /diagnosis/sessions/{session_id}/human-log` endpoint.
  - Payload: `{event: "sop_checked"|"sop_unchecked"|"note_saved"|"archived"|"pending", step?: int, note_len?: int}`.
  - Backend writes to `<session_dir>/human_handling.log`.
  - Frontend calls this endpoint on: SOP checkbox toggle, note save (debounced), 稍后处理, 提交归档.

### Archive directory move
- [ ] When user submits "提交归档" or "标记完成", call backend to rename:
  `logs/sessions/pending/<unit>/<date>/<session>/` → `logs/sessions/archived/<unit>/<date>/<session>/`.
  - Add `POST /diagnosis/sessions/{session_id}/archive` endpoint.
  - Update `meta.json`: set `archived_at` timestamp.
  - Frontend calls it after `addRecord()` / `completePending()`.

### Log retention / cleanup
- [ ] Add a background task (FastAPI lifespan or cron) that:
  - gzips `archived/` session dirs older than 7 days.
  - Deletes gzipped archives older than 90 days.
  - Deletes `pending/` orphan dirs (no finalized_at + older than 24h).

### Root log / monitoring
- [ ] Bridge Python stdlib `logging` → loguru so third-party library warnings
  (LangChain, Chroma, httpx) also appear in `logs/root.log`.
  ```python
  import logging
  from loguru import logger
  class InterceptHandler(logging.Handler):
      def emit(self, record):
          logger.opt(depth=6).log(record.levelname, record.getMessage())
  logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
  ```

### LLM-friendly log index
- [ ] Write a `logs/sessions/index.jsonl` that appends one line per session:
  `{session_id, unit_id, fault_type, risk_level, started_at, finalized_at, dir_rel_path}`.
  - Enables LLM inspection without traversing the directory tree.
  - Update on `create_session_logger` and `finalize`.
