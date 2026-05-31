from __future__ import annotations

import argparse
from pathlib import Path

from .schemas import CLI_ENGINE_CHOICES, normalize_scope


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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kotaemon benchmark toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)

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
    _add_docqa_runtime_options(run_parser)
    run_parser.add_argument(
        "--no-generate",
        action="store_true",
        help="Skip answer generation and return the top retrieved chunk text.",
    )

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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

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
        docqa_citation_mode=args.docqa_citation_mode,
        reasoning_type=args.reasoning_type,
        agent_mode=args.agent_mode,
        task_type=args.task_type,
        artifact_type=args.artifact_type,
        use_generation=not args.no_generate,
    )
    report = run_benchmark(args.manifest, config)
    run_dir = write_reports(report, config.output_dir, config.suite_name)
    print(f"Benchmark complete. Outputs written to {run_dir}")
    return 0
