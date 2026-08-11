#!/usr/bin/env python3
"""Fail when files or history are unsafe for a public repository."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_TRACKED_BYTES = 5_000_000

FORBIDDEN_NAMES = {".env", "credentials", "credentials.json", "id_rsa", "id_ed25519"}
FORBIDDEN_SUFFIXES = {".pem", ".p12", ".pfx", ".key", ".kdbx", ".sqlite"}
MEDIA_SUFFIXES = {".wav", ".mov", ".mp4", ".webm", ".m4a"}
SECRET_PATTERNS = {
    "GitHub token": re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"),
    "GitHub fine-grained token": re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    "OpenAI-style secret": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
}
HOME_PATH = re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+/")
PRIVATE_NETWORK = re.compile(
    r"\b(?:10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.(?:\d{1,3}\.)\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[01])\.(?:\d{1,3}\.)\d{1,3}|"
    r"100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.(?:\d{1,3}\.)\d{1,3})\b"
)
ACTION_REFERENCE = re.compile(r"^\s*-?\s*uses:\s*[^#\s]+@([^#\s]+)", re.MULTILINE)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class Finding:
    path: str
    message: str


def candidate_files(root: Path = ROOT) -> list[Path]:
    """Return tracked plus untracked, non-ignored files."""
    if (root / ".git").is_dir():
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            check=True,
        )
        return [root / os.fsdecode(raw) for raw in result.stdout.split(b"\0") if raw]
    ignored = {".git", ".venv", ".pytest_cache", ".ruff_cache", "build", "__pycache__"}
    return [
        path for path in root.rglob("*") if path.is_file() and not ignored.intersection(path.parts)
    ]


def scan_files(paths: list[Path], root: Path = ROOT) -> list[Finding]:
    """Inspect paths, text, workflow pins, symlinks, and sizes."""
    findings: list[Finding] = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append(Finding(relative, "credential or application state file"))
        if path.suffix.lower() in MEDIA_SUFFIXES:
            findings.append(Finding(relative, "generated media must not be tracked"))
        if path.is_symlink():
            try:
                path.resolve().relative_to(root.resolve())
            except ValueError:
                findings.append(Finding(relative, "symlink points outside the repository"))
            continue
        if not path.is_file():
            continue
        if path.stat().st_size > MAX_TRACKED_BYTES:
            findings.append(Finding(relative, f"file exceeds {MAX_TRACKED_BYTES // 1_000_000} MB"))
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(Finding(relative, f"possible {label}"))
        if relative != "tools/public_repo_check.py":
            if HOME_PATH.search(text):
                findings.append(Finding(relative, "absolute user home path"))
            if PRIVATE_NETWORK.search(text):
                findings.append(Finding(relative, "private network address"))
        if relative.startswith(".github/workflows/") and path.suffix in {".yml", ".yaml"}:
            for match in ACTION_REFERENCE.finditer(text):
                if not FULL_SHA.fullmatch(match.group(1)):
                    findings.append(
                        Finding(relative, f"GitHub Action is not SHA-pinned: @{match.group(1)}")
                    )
    return findings


def scan_history(root: Path = ROOT) -> list[Finding]:
    """Reject public author emails and secret-like Git history."""
    if not (root / ".git").is_dir():
        return []
    result = subprocess.run(
        ["git", "log", "--all", "--format=%H%x00%ae"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    findings: list[Finding] = []
    for line in result.stdout.splitlines():
        commit, _, email = line.partition("\0")
        if email and not email.endswith("@users.noreply.github.com"):
            findings.append(Finding(commit[:12], f"commit author email is public: {email}"))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args(argv)
    findings = scan_files(candidate_files())
    if args.history:
        findings.extend(scan_history())
    if not findings:
        print("Public repository check: OK")
        return 0
    print("Public repository check: FAILED", file=sys.stderr)
    for finding in findings:
        print(f"- {finding.path}: {finding.message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
