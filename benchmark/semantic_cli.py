from __future__ import annotations

import argparse


def add_semantic_evaluator_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--semantic-evaluator",
        default="off",
        help=(
            "Offline semantic answer evaluator: off, on (local Qwen3-8B), "
            "local_qwen3_8b, or a Python callable path."
        ),
    )
    parser.add_argument(
        "--semantic-evaluator-model",
        default="Qwen/Qwen3-8B",
        help="Resolved model name recorded for the semantic evaluator.",
    )
    parser.add_argument(
        "--semantic-evaluator-timeout-seconds",
        type=float,
        default=60.0,
    )
