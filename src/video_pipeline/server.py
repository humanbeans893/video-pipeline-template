"""Threaded HTTP server with single-range byte responses."""

from __future__ import annotations

import http.server
import re
import socketserver
from functools import partial
from pathlib import Path
from typing import BinaryIO

from .config import Project


def parse_byte_range(value: str, size: int) -> tuple[int, int] | None:
    """Parse one RFC 7233-style bytes range."""
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value.strip())
    if not match or size <= 0:
        return None
    start_text, end_text = match.groups()
    if not start_text and not end_text:
        return None
    if start_text:
        start = int(start_text)
        end = int(end_text) if end_text else size - 1
    else:
        suffix = int(end_text)
        if suffix <= 0:
            return None
        start = max(size - suffix, 0)
        end = size - 1
    end = min(end, size - 1)
    return None if start < 0 or start > end or start >= size else (start, end)


class RangeRequestHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler extended with byte range support."""

    range_remaining: int | None = None

    def end_headers(self) -> None:
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_head(self) -> BinaryIO | None:
        value = self.headers.get("Range")
        if not value:
            return super().send_head()
        path = Path(self.translate_path(self.path))
        if not path.is_file():
            return super().send_head()
        size = path.stat().st_size
        parsed = parse_byte_range(value, size)
        if parsed is None:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None
        start, end = parsed
        stream = path.open("rb")
        stream.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        self.range_remaining = end - start + 1
        return stream

    def copyfile(self, source: BinaryIO, outputfile: BinaryIO) -> None:
        remaining = self.range_remaining
        self.range_remaining = None
        if remaining is None:
            super().copyfile(source, outputfile)
            return
        while remaining > 0:
            block = source.read(min(64 * 1024, remaining))
            if not block:
                break
            outputfile.write(block)
            remaining -= len(block)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


class PreviewServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def serve_preview(project: Project, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Serve the build directory until interrupted."""
    handler = partial(RangeRequestHandler, directory=str(project.paths.build))
    with PreviewServer((host, port), handler) as server:
        print(f"http://{host}:{port}/preview.html")
        server.serve_forever()
