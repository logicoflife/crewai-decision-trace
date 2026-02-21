from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .pipeline import CANONICAL_PERSONAS, run_all_personas, run_persona, validate_canonical_inputs
from .verify import verify_outputs
from .viewer import build_offline_viewer


def cmd_demo(persona: str) -> None:
    run_persona(persona)


def cmd_demo_all() -> None:
    run_all_personas()
    build_offline_viewer()


def cmd_verify() -> None:
    verify_outputs()


def cmd_clean_out() -> None:
    out_dir = Path("out")
    if out_dir.exists():
        shutil.rmtree(out_dir)


def cmd_viewer() -> None:
    import streamlit.web.cli as stcli
    import sys

    app = Path("streamlit_viewer/app.py")
    sys.argv = ["streamlit", "run", str(app)]
    stcli.main()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="dt-crewai-demo CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="Run one persona")
    demo.add_argument("--persona", required=True, choices=CANONICAL_PERSONAS)

    sub.add_parser("demo_all", help="Run all personas")
    sub.add_parser("verify", help="Verify outputs")
    sub.add_parser("clean_out", help="Delete out directory")
    sub.add_parser("build_viewer", help="Build offline HTML viewer")
    sub.add_parser("viewer", help="Run streamlit viewer")
    return parser


def main() -> None:
    validate_canonical_inputs()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "demo":
        cmd_demo(args.persona)
    elif args.command == "demo_all":
        cmd_demo_all()
    elif args.command == "verify":
        cmd_verify()
    elif args.command == "clean_out":
        cmd_clean_out()
    elif args.command == "build_viewer":
        build_offline_viewer()
    elif args.command == "viewer":
        cmd_viewer()


if __name__ == "__main__":
    main()
