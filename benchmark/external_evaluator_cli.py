from __future__ import annotations

import argparse


def external_evaluator_map(
    values: list[tuple[str, str]] | None,
) -> dict[str, str]:
    return {adapter_name: backend for adapter_name, backend in values or []}


def add_external_evaluator_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
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


def _external_evaluator_arg(value: str) -> tuple[str, str]:
    adapter_name, separator, backend = str(value or "").partition("=")
    adapter_name = adapter_name.strip()
    backend = backend.strip()
    if not separator or not adapter_name or not backend:
        raise argparse.ArgumentTypeError(
            "--external-evaluator must use ADAPTER=PYTHON_PATH_OR_BUILTIN_ALIAS"
        )
    return adapter_name, backend
