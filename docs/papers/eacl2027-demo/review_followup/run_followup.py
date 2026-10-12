"""Run fresh provider calls in an empty isolated runtime; no stored answers."""

import argparse
import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ORIGINAL = ROOT.parent / "case_study"
MODEL = "gpt-4.1-mini-2025-04-14"
QUESTION = (
    "What value does the pink curve reach at the far right of the main chart? "
    "Give the approximate plotted value."
)


def save(path, value):
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf8",
    )


def prepare(args):
    source = args.source.resolve()
    sys.path[:0] = [
        str(source / "libs" / name) for name in ("ktem", "kotaemon", "slide_cli")
    ]
    sys.path.insert(0, str(ORIGINAL))
    import configuration

    if args.case == "chart":
        configuration.OVERRIDES = configuration.OVERRIDES.replace(
            "deepseek-v4-flash", MODEL
        ).replace("https://api.deepseek.com", "https://api.openai.com/v1")
        os.environ.update(
            MARA_VLM_BASE_URL="https://api.openai.com/v1",
            MARA_VLM_MODEL=MODEL,
            MARA_VLM_API_KEY=os.environ["MARA_CASE_CHAT_API_KEY"],
            MARA_VLM_MAX_OUTPUT_TOKENS="350",
            MARA_VLM_TIMEOUT="60",
        )
    configuration.configure(args.output)
    os.environ["THEFLOW_SETTINGS_MODULE"] = "ktem.default_flowsettings"
    os.chdir(args.output)


def run_turn(runtime, request, label, output, text_calls, visual_calls):
    from ktem.docqa import DocQARequest

    text_calls.clear()
    visual_calls.clear()
    save(output / f"{label}-request.json", request)
    response = runtime.run_turn(DocQARequest(**copy.deepcopy(request))).as_dict()
    save(output / f"{label}-response.json", response)
    save(output / f"{label}-provider-calls.json", text_calls)
    save(output / f"{label}-visual-calls.json", visual_calls)
    print(label, response["answer"], flush=True)


def harbor(runtime, output, text_calls):
    result = runtime.index_paths(
        [str(p) for p in sorted((ORIGINAL / "inputs").glob("*.txt"))]
    )
    save(output / "index.json", result.as_dict())
    assert len(result.successes) == 2 and not result.failures
    ids = {item.name: item.file_id for item in runtime.list_files()}
    for repeat in range(1, 6):
        for label, filename in (
            ("before", "harbor-operations.txt"),
            ("after", "harbor-data-policy.txt"),
        ):
            request = json.loads(
                (ORIGINAL / f"records/{label}-request.json").read_text(encoding="utf8")
            )
            request["selected_file_ids"] = [ids[filename]]
            run_turn(runtime, request, f"{repeat:02d}-{label}", output, text_calls, [])


def chart(runtime, output, text_calls, question):
    from capture_visual import install_observer
    from ktem.docqa.multimodal_index import build_local_page_image_records
    from openai import OpenAI

    visual_calls = install_observer(output)
    excerpt = ROOT / "visual/arctic-page9.pdf"
    result = runtime.index_paths([str(excerpt)])
    save(output / "index.json", result.as_dict())
    assert len(result.successes) == 1 and not result.failures
    file = runtime.list_files()[0]
    records = build_local_page_image_records(
        [{"file_id": file.file_id, "file_name": excerpt.name, "path": str(excerpt)}],
        page_numbers=[1],
        renderer=lambda path, pages, dpi: [str(ROOT / "visual/input-page9.png")],
    )
    request = json.loads(
        (ORIGINAL / "records/after-request.json").read_text(encoding="utf8")
    )
    request.update(
        prompt=question,
        selected_file_ids=[file.file_id],
        verification_mode="off",
        visual_retriever_backend="local_late_interaction",
        visual_generator_backend="local_qwen3_vl",
        page_image_records=records,
        generation_temperature=0.0,
        generation_top_p=1.0,
        generation_seed=20260923,
        route_timeout_seconds=120,
    )
    for label, policy in (
        ("fixed-text", "text"),
        ("automatic", "auto"),
        ("fixed-visual", "page_image"),
    ):
        request["route_policy"] = policy
        run_turn(runtime, request, label, output, text_calls, visual_calls)
    if not visual_calls:
        print("No visual call occurred; no image-removed control can be made.")
        return
    ablation = copy.deepcopy(visual_calls[-1]["request"])
    for message in ablation["messages"]:
        message["content"] = [
            item for item in message["content"] if item.get("type") != "image_url"
        ]
    client = OpenAI(api_key=os.environ["MARA_CASE_CHAT_API_KEY"], timeout=60)
    response = client.chat.completions.create(**ablation)
    save(
        output / "image-removed-ablation.json",
        {"request": ablation, "response": response.model_dump()},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", choices=["harbor", "chart"], required=True)
    parser.add_argument("--question", default=QUESTION)
    args = parser.parse_args()
    args.output = args.output.resolve()
    prepare(args)
    from capture_provider import CALLS
    from slide_cli.docqa_runtime import create_docqa_runtime

    runtime = create_docqa_runtime()
    if args.case == "harbor":
        harbor(runtime, args.output, CALLS)
    else:
        chart(runtime, args.output, CALLS, args.question)


if __name__ == "__main__":
    main()
