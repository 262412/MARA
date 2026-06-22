import json

from ktem.docqa import debug_trace


def test_debug_trace_writes_clean_file_without_console_output(
    monkeypatch,
    tmp_path,
    capsys,
):
    log_path = tmp_path / "mara-stream-debug.jsonl"
    monkeypatch.setenv("MARA_CHAT_STREAM_DEBUG", "1")
    monkeypatch.setenv("MARA_CHAT_STREAM_DEBUG_FILE", str(log_path))
    monkeypatch.setenv("MARA_CHAT_STREAM_DEBUG_CONSOLE", "0")

    debug_trace.log_event("debug.file_output", answer=debug_trace.summarize_text("总览"))

    assert capsys.readouterr().out == ""
    line = log_path.read_text(encoding="utf-8").strip()
    assert line.startswith("[MARA_CHAT_STREAM_DEBUG] ")
    payload = json.loads(line.removeprefix("[MARA_CHAT_STREAM_DEBUG] "))
    assert payload["event"] == "debug.file_output"
    assert payload["answer"]["head"] == "总览"
