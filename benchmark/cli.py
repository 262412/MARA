from __future__ import annotations

import argparse
from pathlib import Path

from .schemas import (
    BENCHMARK_PROMPT_POLICIES,
    BENCHMARK_PROMPT_PROFILES,
    CLI_ENGINE_CHOICES,
    normalize_scope,
)


def _add_docqa_runtime_options(run_parser: argparse.ArgumentParser) -> None:
    run_parser.add_argument(
        "--docqa-citation-mode",
        choices=["highlight", "inline", "off"],
        help=(
            "Override DocQA citation mode. Use 'off' for LLMs that do not "
            "support OpenAI-compatible tool_choice/function calling."
        ),
    )
    run_parser.add_argument(
        "--reasoning",
        dest="reasoning_type",
        help="DocQA reasoning mode, for example 'mara'.",
    )
    run_parser.add_argument(
        "--agent-mode",
        choices=["auto", "fast", "thorough"],
        help="MARA agent mode for DocQA runtime benchmarks.",
    )
    run_parser.add_argument(
        "--task-type",
        help="MARA task type, for example 'qa', 'quiz', or 'slide_outline'.",
    )
    run_parser.add_argument(
        "--artifact-type",
        help="MARA Studio artifact type to request during DocQA benchmarks.",
    )


def _add_artifact_detail_option(run_parser: argparse.ArgumentParser) -> None:
    run_parser.add_argument(
        "--artifact-detail",
        default="compact",
        choices=["compact", "full"],
        help="Write compact artifacts by default; use full for small debug runs.",
    )


def _add_benchmark_prompt_options(run_parser: argparse.ArgumentParser) -> None:
    run_parser.add_argument(
        "--benchmark-prompt-policy",
        default="benchmark_v1",
        choices=BENCHMARK_PROMPT_POLICIES,
        help="Benchmark prompt contract policy; raw preserves historical direct prompt forwarding.",
    )
    run_parser.add_argument(
        "--benchmark-prompt-profile",
        default="auto",
        choices=BENCHMARK_PROMPT_PROFILES,
        help="Benchmark answer-style profile; auto selects from dataset/modality metadata.",
    )


def _external_evaluator_arg(value: str) -> tuple[str, str]:
    adapter_name, separator, backend = str(value or "").partition("=")
    adapter_name = adapter_name.strip()
    backend = backend.strip()
    if not separator or not adapter_name or not backend:
        raise argparse.ArgumentTypeError(
            "--external-evaluator must use ADAPTER=PYTHON_PATH_OR_BUILTIN_ALIAS"
        )
    return adapter_name, backend


def _external_evaluator_map(values: list[tuple[str, str]] | None) -> dict[str, str]:
    return {adapter_name: backend for adapter_name, backend in values or []}


def _add_external_evaluator_options(run_parser: argparse.ArgumentParser) -> None:
    run_parser.add_argument(
        "--external-evaluator",
        action="append",
        default=[],
        type=_external_evaluator_arg,
        metavar="ADAPTER=BACKEND",
        help=(
            "Configure an external research evaluator backend for this run. "
            "May be repeated, for example alce=package.module.evaluator or "
            "alce=builtin:alce_proxy."
        ),
    )


def _add_run_command(subparsers: argparse._SubParsersAction) -> None:
    run_parser = subparsers.add_parser("run", help="Run a benchmark suite")
    run_parser.add_argument(
        "--manifest", required=True, help="Normalized manifest path"
    )
    run_parser.add_argument("--suite-name", default="kotaemon-benchmark")
    run_parser.add_argument(
        "--engine",
        default="legacy_text_rag",
        choices=CLI_ENGINE_CHOICES,
    )
    run_parser.add_argument(
        "--scope",
        default="document",
        choices=["page", "document", "multi_document", "multi-document"],
    )
    run_parser.add_argument("--route", default="all")
    run_parser.add_argument("--cost-profile")
    run_parser.add_argument(
        "--cache-mode",
        default="warm",
        choices=["warm", "cold", "bypass"],
        help=(
            "warm reuses benchmark caches, cold starts from an empty run-local "
            "cache, bypass disables benchmark parse cache."
        ),
    )
    run_parser.add_argument(
        "--output-dir",
        default="benchmark/artifacts",
        help="Directory for benchmark outputs",
    )
    _add_artifact_detail_option(run_parser)
    _add_benchmark_prompt_options(run_parser)
    _add_external_evaluator_options(run_parser)
    run_parser.add_argument(
        "--reader-mode",
        default="default",
        choices=["default", "adobe", "azure-di", "docling"],
    )
    run_parser.add_argument(
        "--retrieval-mode",
        default="hybrid",
        choices=["vector", "text", "hybrid"],
    )
    run_parser.add_argument("--chunk-size", type=int, default=1024)
    run_parser.add_argument("--chunk-overlap", type=int, default=256)
    run_parser.add_argument("--top-k", type=int, default=5)
    run_parser.add_argument("--max-context-length", type=int, default=16000)
    run_parser.add_argument("--embedding-name")
    run_parser.add_argument("--reranker-name")
    run_parser.add_argument("--llm-name")
    run_parser.add_argument(
        "--limit",
        type=int,
        help="Run at most this many selected examples after sampling and sharding.",
    )
    run_parser.add_argument(
        "--sample-seed",
        type=int,
        help="Deterministically shuffle examples before sharding/limiting.",
    )
    run_parser.add_argument(
        "--shard-index",
        type=int,
        help="Zero-based shard index to run.",
    )
    run_parser.add_argument(
        "--num-shards",
        type=int,
        help="Total number of shards for distributed benchmark runs.",
    )
    _add_docqa_runtime_options(run_parser)
    run_parser.add_argument(
        "--no-generate",
        action="store_true",
        help="Skip answer generation and return the top retrieved chunk text.",
    )


def _add_rescore_command(subparsers: argparse._SubParsersAction) -> None:
    rescore_parser = subparsers.add_parser(
        "rescore-artifact",
        help="Add MARA-oriented scores to an existing benchmark artifact run",
    )
    rescore_parser.add_argument("--run-dir", required=True)
    rescore_parser.add_argument("--output-dir", required=True)
    rescore_parser.add_argument("--suite-name")
    _add_artifact_detail_option(rescore_parser)
    _add_external_evaluator_options(rescore_parser)

    batch_parser = subparsers.add_parser(
        "rescore-artifacts",
        help="Add MARA-oriented scores to direct child artifact runs",
    )
    batch_parser.add_argument("--input-dir", required=True)
    batch_parser.add_argument("--output-dir", required=True)
    batch_parser.add_argument("--suite-prefix", default="rescored")
    _add_artifact_detail_option(batch_parser)
    _add_external_evaluator_options(batch_parser)


def _add_existing_normalizer_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    local_parser = subparsers.add_parser(
        "normalize-format-robustness",
        help="Convert a local PDF/DOCX/PPTX QA folder into a normalized manifest",
    )
    local_parser.add_argument("--source-dir", required=True)
    local_parser.add_argument("--output", required=True)

    finance_parser = subparsers.add_parser(
        "normalize-financebench",
        help="Convert FinanceBench open-source files into a normalized manifest",
    )
    finance_parser.add_argument("--source-dir", required=True)
    finance_parser.add_argument("--output", required=True)
    finance_parser.add_argument("--pdf-root")

    slide_parser = subparsers.add_parser(
        "normalize-slidevqa",
        help="Convert SlideVQA annotations into a normalized manifest",
    )
    slide_parser.add_argument("--annotations", required=True)
    slide_parser.add_argument("--documents-root", required=True)
    slide_parser.add_argument("--output", required=True)

    slide_parquet_parser = subparsers.add_parser(
        "normalize-slidevqa-parquet",
        help="Convert Hugging Face SlideVQA parquet rows into a normalized manifest",
    )
    slide_parquet_parser.add_argument("--source", required=True)
    slide_parquet_parser.add_argument("--output", required=True)


def _add_thesis_converter_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    qasper_parser = subparsers.add_parser(
        "normalize-qasper",
        help="Convert QASPER raw JSON into a normalized manifest",
    )
    qasper_parser.add_argument("--source", required=True)
    qasper_parser.add_argument("--output", required=True)

    mmdocrag_parser = subparsers.add_parser(
        "normalize-mmdocrag",
        help="Convert MMDocRAG JSONL into a normalized manifest",
    )
    mmdocrag_parser.add_argument("--source", required=True)
    mmdocrag_parser.add_argument("--output", required=True)
    mmdocrag_parser.add_argument("--documents-root")

    vidore_parser = subparsers.add_parser(
        "normalize-vidore",
        help="Convert ViDoRe JSON/JSONL/parquet rows into a normalized manifest",
    )
    vidore_parser.add_argument("--source", required=True)
    vidore_parser.add_argument("--output", required=True)
    vidore_parser.add_argument("--documents-root")

    ragtruth_parser = subparsers.add_parser(
        "normalize-ragtruth",
        help="Convert RAGTruth source_info/response JSONL files into a manifest",
    )
    ragtruth_parser.add_argument("--source-info", required=True)
    ragtruth_parser.add_argument("--responses", required=True)
    ragtruth_parser.add_argument("--output", required=True)

    alce_parser = subparsers.add_parser(
        "normalize-alce",
        help="Convert ALCE ASQA/ELI5/Qampari JSON into a normalized manifest",
    )
    alce_parser.add_argument("--source", required=True)
    alce_parser.add_argument("--output", required=True)


def _add_manifest_template_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    template_parser = subparsers.add_parser(
        "apply-route-template",
        help="Combine a dataset manifest with a route template manifest",
    )
    template_parser.add_argument("--manifest", required=True)
    template_parser.add_argument("--template", required=True)
    template_parser.add_argument("--output", required=True)
    template_parser.add_argument("--dataset-name")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kotaemon benchmark toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_run_command(subparsers)
    _add_rescore_command(subparsers)
    _add_existing_normalizer_commands(subparsers)
    _add_thesis_converter_commands(subparsers)
    _add_manifest_template_commands(subparsers)
    return parser


def _handle_rescore_command(args: argparse.Namespace) -> int | None:
    if args.command not in {"rescore-artifact", "rescore-artifacts"}:
        return None

    from .artifact_rescoring import rescore_artifact_run, rescore_artifact_runs

    if args.command == "rescore-artifacts":
        run_dirs = rescore_artifact_runs(
            args.input_dir,
            args.output_dir,
            suite_prefix=args.suite_prefix,
            artifact_detail=args.artifact_detail,
            external_evaluators=_external_evaluator_map(args.external_evaluator),
        )
        print(f"Rescored {len(run_dirs)} artifact runs into {args.output_dir}")
        return 0

    run_dir = rescore_artifact_run(
        args.run_dir,
        args.output_dir,
        suite_name=args.suite_name,
        artifact_detail=args.artifact_detail,
        external_evaluators=_external_evaluator_map(args.external_evaluator),
    )
    print(f"Rescored artifact written to {run_dir}")
    return 0


def _handle_manifest_template_command(args: argparse.Namespace) -> int | None:
    if args.command != "apply-route-template":
        return None

    from .manifest_templates import apply_route_template

    output_path = apply_route_template(
        args.manifest,
        args.template,
        args.output,
        dataset_name=args.dataset_name,
    )
    print(f"Manifest written to {output_path}")
    return 0


def _handle_normalizer_command(args: argparse.Namespace) -> int | None:
    if args.command == "normalize-format-robustness":
        from .normalizers import normalize_format_robustness_manifest

        output_path = normalize_format_robustness_manifest(args.source_dir, args.output)
        print(f"Manifest written to {output_path}")
        return 0

    if args.command == "normalize-financebench":
        from .normalizers import normalize_financebench_manifest

        output_path = normalize_financebench_manifest(
            args.source_dir, args.output, args.pdf_root
        )
        print(f"Manifest written to {output_path}")
        return 0

    if args.command == "normalize-slidevqa":
        from .normalizers import normalize_slidevqa_manifest

        output_path = normalize_slidevqa_manifest(
            args.annotations, args.documents_root, args.output
        )
        print(f"Manifest written to {output_path}")
        return 0

    if args.command == "normalize-slidevqa-parquet":
        from .converters.slidevqa import normalize_slidevqa_parquet_manifest

        output_path = normalize_slidevqa_parquet_manifest(args.source, args.output)
        print(f"Manifest written to {output_path}")
        return 0

    if args.command == "normalize-qasper":
        from .converters.qasper import normalize_qasper_manifest

        output_path = normalize_qasper_manifest(args.source, args.output)
        print(f"Manifest written to {output_path}")
        return 0

    if args.command == "normalize-mmdocrag":
        from .converters.mmdocrag import normalize_mmdocrag_manifest

        output_path = normalize_mmdocrag_manifest(
            args.source, args.output, args.documents_root
        )
        print(f"Manifest written to {output_path}")
        return 0

    if args.command == "normalize-vidore":
        from .converters.vidore import normalize_vidore_manifest

        output_path = normalize_vidore_manifest(
            args.source, args.output, args.documents_root
        )
        print(f"Manifest written to {output_path}")
        return 0

    if args.command == "normalize-ragtruth":
        from .converters.ragtruth import normalize_ragtruth_manifest

        output_path = normalize_ragtruth_manifest(
            args.source_info, args.responses, args.output
        )
        print(f"Manifest written to {output_path}")
        return 0

    if args.command == "normalize-alce":
        from .converters.alce import normalize_alce_manifest

        output_path = normalize_alce_manifest(args.source, args.output)
        print(f"Manifest written to {output_path}")
        return 0

    return None


def _run_benchmark_command(args: argparse.Namespace) -> int:
    from .reports import write_reports
    from .runner import run_benchmark
    from .schemas import BenchmarkConfig

    config = BenchmarkConfig(
        suite_name=args.suite_name,
        output_dir=Path(args.output_dir),
        engine=args.engine,
        scope=normalize_scope(args.scope),
        route=args.route,
        cost_profile=args.cost_profile,
        cache_mode=args.cache_mode,
        reader_mode=args.reader_mode,
        retrieval_mode=args.retrieval_mode,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        top_k=args.top_k,
        max_context_length=args.max_context_length,
        embedding_name=args.embedding_name,
        reranker_name=args.reranker_name,
        llm_name=args.llm_name,
        artifact_detail=args.artifact_detail,
        benchmark_prompt_policy=args.benchmark_prompt_policy,
        benchmark_prompt_profile=args.benchmark_prompt_profile,
        external_evaluators=_external_evaluator_map(args.external_evaluator),
        limit=args.limit,
        sample_seed=args.sample_seed,
        shard_index=args.shard_index,
        num_shards=args.num_shards,
        docqa_citation_mode=args.docqa_citation_mode,
        reasoning_type=args.reasoning_type,
        agent_mode=args.agent_mode,
        task_type=args.task_type,
        artifact_type=args.artifact_type,
        use_generation=not args.no_generate,
    )
    report = run_benchmark(args.manifest, config)
    run_dir = write_reports(
        report,
        config.output_dir,
        config.suite_name,
        artifact_detail=config.artifact_detail,
    )
    print(f"Benchmark complete. Outputs written to {run_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    template_result = _handle_manifest_template_command(args)
    if template_result is not None:
        return template_result
    rescore_result = _handle_rescore_command(args)
    if rescore_result is not None:
        return rescore_result
    normalizer_result = _handle_normalizer_command(args)
    if normalizer_result is not None:
        return normalizer_result
    return _run_benchmark_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
