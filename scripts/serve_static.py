"""Serve the static edition of Phase Navigator with nothing but Python.

Only the standard library is used, so this file also works on a machine without the
project virtual environment: ``build_static_site`` copies it into ``static_site/``.

Compared with ``python -m http.server`` it
* sends the right MIME types on every system (a web worker is refused when ``.js`` files
  are served as ``text/plain``, which some Windows registries cause);
* makes browsers re-check the page and scripts, so an update is never hidden by a cache;
* serves several browsers at once and prints the addresses to open.

Usage (from the repository root, with the project virtual environment's Python)::

    python -m scripts.serve_static                 # http://127.0.0.1:8080/ (this PC only)
    python -m scripts.serve_static --lan           # also reachable from the local network
    python -m scripts.serve_static --port 9000

Copied to another machine::

    python serve_static.py --lan
"""
from __future__ import annotations

import argparse
import functools
import socket
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List, Optional, Sequence

# Fixed so the result does not depend on the operating system's MIME configuration.
MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".gz": "application/gzip",
    ".zip": "application/zip",
    ".wasm": "application/wasm",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}

# Files that change with a new build and must not be reused from a stale browser cache.
REVALIDATED_SUFFIXES = {".html", ".js", ".css", ".json", ".zip"}


class StaticHandler(SimpleHTTPRequestHandler):
    """Request handler with fixed MIME types, revalidating caches and no content encoding."""

    def guess_type(self, path) -> str:
        """
        Return the Content-Type of a file.

        Args:
            path: Path of the requested file.

        Returns:
            A MIME type from ``MIME_TYPES``, or the standard library's guess for other files.
        """
        suffix = Path(str(path)).suffix.lower()
        return MIME_TYPES.get(suffix) or super().guess_type(path)

    def end_headers(self) -> None:
        """Add ``Cache-Control: no-cache`` to files that change between builds."""
        if Path(self.path.split("?", 1)[0]).suffix.lower() in REVALIDATED_SUFFIXES or self.path.endswith("/"):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()


class StaticServer(ThreadingHTTPServer):
    """Threaded server that refuses a port another program already listens on."""

    # On Windows SO_REUSEADDR lets a second socket bind a busy port without any error, so
    # the server would start but never receive a request. Elsewhere the default is harmless.
    allow_reuse_address = sys.platform != "win32"


def lan_addresses() -> List[str]:
    """
    Find the IPv4 address this machine uses on the local network.

    Returns:
        A list with that address, or an empty list when none can be determined.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # A UDP "connect" sends nothing; it only makes the OS choose the outgoing interface.
        probe.connect(("10.255.255.255", 1))
        address = probe.getsockname()[0]
    except OSError:
        return []
    finally:
        probe.close()
    return [] if address.startswith("127.") else [address]


def default_directory() -> Path:
    """
    Choose the folder to serve when ``--dir`` is not given.

    Returns:
        The folder of this script when it was copied into a built site, else ``static_site``.
    """
    here = Path(__file__).resolve().parent
    return here if (here / "index.html").is_file() else Path("static_site")


def make_server(directory: Path, host: str, port: int) -> StaticServer:
    """
    Create the HTTP server (without starting it).

    Args:
        directory: Folder to serve.
        host: Address to listen on.
        port: Port to listen on; 0 picks a free port.

    Returns:
        The bound server.

    Raises:
        OSError: If the port is already in use or cannot be bound.
    """
    handler = functools.partial(StaticHandler, directory=str(directory))
    return StaticServer((host, port), handler)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    Command line entry point.

    Args:
        argv: Arguments; defaults to ``sys.argv[1:]``.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", default=None, help="Folder to serve (default: static_site, or this script's folder).")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080).")
    parser.add_argument(
        "--lan",
        action="store_true",
        help="Listen on all network interfaces so other computers on the local network can connect. "
        "Without it only this computer can connect.",
    )
    args = parser.parse_args(argv)

    directory = Path(args.dir) if args.dir else default_directory()
    if not (directory / "index.html").is_file():
        print(
            f"error: {directory} has no index.html. Build the site first: python -m scripts.build_static_site",
            file=sys.stderr,
        )
        return 1
    if not (directory / "data" / "manifest.json").is_file():
        print(
            f"warning: {directory / 'data'} has no manifest.json, so diagrams cannot be calculated yet. "
            "Download the data first (see the README).",
            file=sys.stderr,
        )

    host = "0.0.0.0" if args.lan else "127.0.0.1"
    try:
        server = make_server(directory, host, args.port)
    except OSError as error:
        print(f"error: cannot listen on {host}:{args.port} ({error.strerror}). Try another port with --port.", file=sys.stderr)
        return 1

    port = server.server_address[1]
    print(f"Serving {directory.resolve()}")
    print(f"  This computer:  http://127.0.0.1:{port}/")
    if args.lan:
        for address in lan_addresses():
            print(f"  Local network:  http://{address}:{port}/")
    else:
        print("  (Only this computer can connect. Add --lan to allow the local network.)")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
