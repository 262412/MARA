from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .config import SlideAgentConfig

if TYPE_CHECKING:
    from .deck import DeckPatch


def SlideAgentRunner(*args, **kwargs):
    from .agent import SlideAgentRunner as _SlideAgentRunner

    return _SlideAgentRunner(*args, **kwargs)


def SlideSessionStore(*args, **kwargs):
    from .session_store import SlideSessionStore as _SlideSessionStore

    return _SlideSessionStore(*args, **kwargs)


def apply_deck_patch(*args, **kwargs):
    from .deck import apply_deck_patch as _apply_deck_patch

    return _apply_deck_patch(*args, **kwargs)


def collect_doctor_payload(config_path: str = "modelcli.yml") -> dict[str, Any]:
    from kotaemon.modelcli import build_registry, load_runtime_config

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
        "export_pdf": bool(python_pptx and soffice),
    }


def _patch_to_dict(patch: "DeckPatch | None") -> dict[str, Any] | None:
    if patch is None:
        return None
    return patch.as_dict()


def _patch_from_dict(payload: dict[str, Any] | None) -> "DeckPatch | None":
    from .deck import DeckPatch, TextReplaceOp

    if not payload:
        return None
    edits = []
    for item in payload.get("edits") or []:
        if not isinstance(item, dict):
            continue
        try:
            edits.append(
                TextReplaceOp(
                    slide_number=int(item["slide_number"]),
                    target_id=str(item["target_id"]),
                    before_text=(
                        None if item.get("before_text") is None else str(item.get("before_text"))
                    ),
                    after_text=str(item["after_text"]),
                )
            )
        except Exception:
            continue
    return DeckPatch(summary=str(payload.get("summary", "")), edits=edits)


def _write_patch_artifact(session, patch: "DeckPatch | None") -> str:
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


def _resolve_output_path(input_path: str, output_path: str | None = None) -> Path:
    if output_path:
        return Path(output_path)
    source = Path(input_path)
    return source.with_name(f"{source.stem}.rewritten.pptx")


def build_slide_config(
    *,
    cwd: str | None = None,
    approval_policy: str = "confirm",
    shell_timeout_sec: int = 15,
    model: str = "gpt-4o-mini",
    provider: str | None = None,
    config_path: str = "modelcli.yml",
    max_iterations: int = 4,
    apply_mode: str = "preview",
    output_path: str | None = None,
) -> SlideAgentConfig:
    return SlideAgentConfig(
        cwd=cwd,
        approval_policy=approval_policy,
        shell_timeout_sec=shell_timeout_sec,
        model=model,
        provider=provider,
        config_path=config_path,
        max_iterations=max_iterations,
        apply_mode=apply_mode,
        output_path=output_path,
    )


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
    apply_mode: str = "preview",
    approval_policy: str = "confirm",
    shell_timeout_sec: int = 15,
    max_iterations: int = 4,
    base_dir: str | Path | None = None,
) -> dict[str, Any]:
    config = build_slide_config(
        cwd=cwd,
        approval_policy=approval_policy,
        shell_timeout_sec=shell_timeout_sec,
        model=model,
        provider=provider,
        config_path=config_path,
        max_iterations=max_iterations,
        apply_mode="preview" if dry_run else apply_mode,
        output_path=output_path,
    )
    store = SlideSessionStore(base_dir=base_dir) if base_dir is not None else SlideSessionStore()
    session = store.load_session(session_id) if session_id else None
    if session is None:
        session = store.create_session(
            mode="run",
            title=f"Run: {Path(input_path).name}",
            input_path=input_path,
            prompt=prompt,
            cwd=cwd or "",
            metadata={"config": config.as_dict()},
        )

    session = store.append_event(
        session.session_id,
        {"role": "user", "kind": "prompt", "content": prompt},
    )
    runner = SlideAgentRunner(
        input_path=input_path,
        config=config,
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
    suggested_output_path = ""
    apply_result: dict[str, Any] | None = None
    if patch and patch.edits:
        suggested_output_path = str(_resolve_output_path(input_path, config.output_path))
    if patch and patch.edits and config.should_apply:
        destination = _resolve_output_path(input_path, config.output_path)
        result = apply_deck_patch(input_path, patch, output_path=destination)
        applied_output_path = str(result.output_path)
        apply_result = result.as_dict()

    patch_path = _write_patch_artifact(session, patch)
    can_apply = bool(patch and patch.edits and not applied_output_path)

    session = store.append_event(
        session.session_id,
        {
            "role": "assistant",
            "kind": "final",
            "content": assistant_response,
            "patch": _patch_to_dict(patch),
            "patch_path": patch_path,
            "output_path": applied_output_path,
            "suggested_output_path": suggested_output_path,
            "apply_mode": config.apply_mode,
        },
    )
    store.update_session(
        session.session_id,
        status="completed",
        output_path=applied_output_path,
        prompt=prompt,
    )

    if dry_run:
        mode = "dry-run"
    elif applied_output_path:
        mode = "apply"
    elif can_apply and config.needs_confirmation:
        mode = "confirm"
    else:
        mode = "preview"

    return {
        "status": "ok",
        "mode": mode,
        "apply_mode": config.apply_mode,
        "response": assistant_response,
        "output_path": applied_output_path,
        "suggested_output_path": suggested_output_path,
        "can_apply": can_apply,
        "patch": _patch_to_dict(patch),
        "patch_path": patch_path,
        "apply_result": apply_result,
        "observations": list(agent_result["observations"]),
        "session_id": session.session_id,
        "input_path": input_path,
    }


def apply_session_patch(
    session_id: str,
    *,
    output_path: str | None = None,
    base_dir: str | Path | None = None,
) -> dict[str, Any]:
    store = SlideSessionStore(base_dir=base_dir) if base_dir is not None else SlideSessionStore()
    session = store.load_session(session_id)
    if session is None:
        raise FileNotFoundError(f"Session '{session_id}' was not found.")

    final_event = next(
        (
            event
            for event in reversed(session.events)
            if event.get("kind") == "final" and isinstance(event.get("patch"), dict)
        ),
        None,
    )
    if final_event is None:
        raise ValueError(f"Session '{session_id}' does not contain an applyable patch.")

    patch = _patch_from_dict(final_event.get("patch"))
    if patch is None or not patch.edits:
        raise ValueError(f"Session '{session_id}' does not contain an applyable patch.")

    destination = _resolve_output_path(session.input_path, output_path)
    result = apply_deck_patch(session.input_path, patch, output_path=destination)
    store.append_event(
        session.session_id,
        {
            "role": "assistant",
            "kind": "apply",
            "content": f"Applied patch to {result.output_path}",
            "output_path": str(result.output_path),
        },
    )
    store.update_session(
        session.session_id,
        output_path=str(result.output_path),
        status="completed",
    )
    payload = result.as_dict()
    payload["session_id"] = session_id
    return payload
