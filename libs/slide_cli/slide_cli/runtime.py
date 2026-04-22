from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kotaemon.modelcli import build_registry, load_runtime_config

from .agent import SlideAgentRunner
from .deck import DeckPatch, apply_deck_patch
from .session_store import SlideSessionStore


def collect_doctor_payload(config_path: str = "modelcli.yml") -> dict[str, Any]:
    resolved_config_path = (
        str(Path(config_path).resolve()) if config_path and Path(config_path).exists() else ""
    )
    cfg = load_runtime_config(config_path if resolved_config_path else None)
    registry = build_registry()
    availability = registry.availability(cfg)
    soffice = os.environ.get("SOFFICE_PATH") or shutil.which("soffice")

    try:
        import pptx  # noqa: F401
    except Exception:
        python_pptx = False
    else:
        python_pptx = True

    return {
        "ok": python_pptx,
        "config_path": resolved_config_path,
        "providers": {
            name: {"available": available, "reason": reason}
            for name, (available, reason) in availability.items()
        },
        "python_pptx": python_pptx,
        "libreoffice": bool(soffice),
        "soffice_path": str(soffice or ""),
    }


def _patch_to_dict(patch: DeckPatch | None) -> dict[str, Any] | None:
    if patch is None:
        return None
    return patch.as_dict()


def _write_patch_artifact(session, patch: DeckPatch | None) -> str:
    if patch is None:
        return ""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    patch_path = session.patches_dir / f"patch-{timestamp}.json"
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text(
        json.dumps(patch.as_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(patch_path)


def run_slide_task(
    *,
    input_path: str,
    prompt: str,
    output_path: str | None = None,
    dry_run: bool = False,
    model: str = "gpt-4o-mini",
    provider: str | None = None,
    config_path: str = "modelcli.yml",
    cwd: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    store = SlideSessionStore()
    session = store.load_session(session_id) if session_id else None
    if session is None:
        session = store.create_session(
            mode="run",
            title=f"Run: {Path(input_path).name}",
            input_path=input_path,
            prompt=prompt,
            cwd=cwd or "",
            metadata={"model": model, "provider": provider or ""},
        )

    session = store.append_event(
        session.session_id,
        {"role": "user", "kind": "prompt", "content": prompt},
    )
    runner = SlideAgentRunner(
        input_path=input_path,
        model=model,
        provider=provider,
        config_path=config_path,
        cwd=cwd,
    )
    agent_result = runner.run(prompt, history=session.events)
    patch = agent_result["patch"]
    assistant_response = str(agent_result["assistant_response"]).strip() or "No response generated."

    for observation in agent_result["observations"]:
        session = store.append_event(
            session.session_id,
            {
                "role": "assistant",
                "kind": "tool",
                "tool": observation["tool"],
                "content": observation["output"],
            },
        )

    applied_output_path = ""
    if patch and patch.edits and not dry_run:
        destination = (
            Path(output_path)
            if output_path
            else Path(input_path).with_name(f"{Path(input_path).stem}.rewritten.pptx")
        )
        result = apply_deck_patch(input_path, patch, output_path=destination)
        applied_output_path = str(result.output_path)

    patch_path = _write_patch_artifact(session, patch)

    session = store.append_event(
        session.session_id,
        {
            "role": "assistant",
            "kind": "final",
            "content": assistant_response,
            "patch": _patch_to_dict(patch),
            "patch_path": patch_path,
            "output_path": applied_output_path,
        },
    )
    store.update_session(
        session.session_id,
        status="completed",
        output_path=applied_output_path,
        prompt=prompt,
    )

    return {
        "status": "ok",
        "mode": "dry-run" if dry_run or not applied_output_path else "apply",
        "response": assistant_response,
        "output_path": applied_output_path,
        "patch": _patch_to_dict(patch),
        "patch_path": patch_path,
        "observations": list(agent_result["observations"]),
        "session_id": session.session_id,
        "input_path": input_path,
    }
