"""Command-line interface for the full video pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .audio import synthesize_project
from .characters import build_character_overlay
from .config import PipelineError, load_project
from .doctor import run_doctor
from .movie import build_movie
from .preview import build_preview
from .rendering import render_cuts
from .server import serve_preview
from .timeline import build_shotlist, scaffold_missing_cuts, validate_cut_contract


def parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    root = argparse.ArgumentParser(prog="video-pipeline")
    root.add_argument("--root", type=Path, default=None, help="project root (default: auto-detect)")
    commands = root.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="check external tools and configuration")
    doctor.add_argument("--offline", action="store_true", help="skip the VOICEVOX connection check")
    commands.add_parser("validate", help="validate YAML and cut modules")
    commands.add_parser("synthesize", help="generate speech, subtitles, and timing")
    commands.add_parser("shotlist", help="derive the shot list")
    commands.add_parser("scaffold", help="create modules for missing cuts")
    render = commands.add_parser("render", help="render one cut or all cuts")
    group = render.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("--cut")
    commands.add_parser("characters", help="render the lip-sync overlay")
    commands.add_parser("preview", help="generate browser preview files")
    serve = commands.add_parser("serve", help="serve the browser preview")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    movie = commands.add_parser("build", help="assemble the final MP4")
    movie.add_argument("--draft", action="store_true")
    movie.add_argument("--no-subs", action="store_true")
    commands.add_parser("all", help="run the complete pipeline")
    return root


def main(argv: list[str] | None = None) -> int:
    """Run a CLI command and translate user errors into exit status 1."""
    args = parser().parse_args(argv)
    try:
        project = load_project(args.root)
        if args.command == "doctor":
            run_doctor(project, check_voicevox=not args.offline)
        elif args.command == "validate":
            validate_cut_contract(project)
            print("✓ configuration and cut contract")
        elif args.command == "synthesize":
            synthesize_project(project)
        elif args.command == "shotlist":
            build_shotlist(project)
        elif args.command == "scaffold":
            created = scaffold_missing_cuts(project)
            print(f"created {created} cut module(s)")
        elif args.command == "render":
            render_cuts(project, selected=args.cut if not args.all else None)
        elif args.command == "characters":
            build_character_overlay(project)
        elif args.command == "preview":
            build_preview(project)
        elif args.command == "serve":
            serve_preview(project, args.host, args.port)
        elif args.command == "build":
            build_movie(project, draft=args.draft, subtitles=not args.no_subs)
        elif args.command == "all":
            run_doctor(project)
            synthesize_project(project)
            build_shotlist(project)
            render_cuts(project)
            build_character_overlay(project)
            build_preview(project)
            build_movie(project)
        return 0
    except KeyboardInterrupt:
        print("\nstopped", file=sys.stderr)
        return 130
    except (PipelineError, FileNotFoundError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
