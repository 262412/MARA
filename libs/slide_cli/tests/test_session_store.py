from slide_cli.session_store import SlideSessionStore


def test_session_store_round_trip(tmp_path):
    store = SlideSessionStore(base_dir=tmp_path)

    created = store.create_session(
        mode="chat",
        title="Rewrite QBR deck",
        input_path="D:/decks/qbr.pptx",
        prompt="Rewrite for executive audience",
        cwd="D:/decks",
    )
    store.append_event(
        created.session_id,
        {
            "role": "assistant",
            "kind": "final",
            "content": "Prepared edits.",
        },
    )

    loaded = store.load_session(created.session_id)
    listed = store.list_sessions()

    assert loaded is not None
    assert loaded.session_id == created.session_id
    assert loaded.mode == "chat"
    assert loaded.input_path == "D:/decks/qbr.pptx"
    assert loaded.events[-1]["content"] == "Prepared edits."
    assert listed[0].session_id == created.session_id
    assert listed[0].artifacts_dir.exists()
    assert listed[0].transcript_path.exists()
