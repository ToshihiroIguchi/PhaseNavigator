"""Assemble the static edition of Phase Navigator.

The output folder can be served by any static web server (GitHub Pages, Netlify,
``python -m http.server``) and needs neither Python nor an API key on the server:

* ``index.html``      the page, rendered from the same templates as the server edition;
* ``static/``         CSS, JavaScript and images;
* ``vendor/``         plotly.js (the bundle that ships with the Python plotly package);
* ``phasecore.zip``   the calculation code that runs in the browser through Pyodide;
* ``data/``           the pre-downloaded Materials Project data (built separately with
                      ``scripts/build_static_data.py``; not touched by this script).

Usage (from the repository root, with the project virtual environment's Python)::

    python -m scripts.build_static_site
    python -m http.server --directory static_site 8080
"""
from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path
from typing import List, Optional, Sequence

import plotly
from jinja2 import Environment, FileSystemLoader
from plotly.offline import get_plotlyjs_version

from app.core.config import settings

ROOT = Path(__file__).resolve().parent.parent

# Pyodide release loaded from the jsDelivr CDN. The hash is the SHA-384 of
# ``pyodide.js`` for exactly this version; update both together.
PYODIDE_VERSION = "314.0.8"
PYODIDE_URL = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
PYODIDE_SRI = "sha384-0Tw0jFeRF+UzB1HbzjzDi5ZNMyMclQPHmYkEquv9V+lAj/rZBHxu1c35Uq28kDPo"

# Fixed timestamp so the same sources always give the same zip bytes.
ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def render_index() -> str:
    """
    Render the page with relative asset paths and the static-edition switches on.

    Returns:
        The HTML of ``index.html``.
    """
    env = Environment(loader=FileSystemLoader(str(ROOT / "templates")), autoescape=True)
    env.globals.update(
        app_version=settings.app_version,
        plotly_js_version=get_plotlyjs_version(),
        static_edition=True,
        static_prefix="static",
        vendor_prefix="vendor",
        pyodide_url=PYODIDE_URL,
        pyodide_sri=PYODIDE_SRI,
    )
    return env.get_template("index.html").render()


def phasecore_files() -> List[Path]:
    """
    List the files of the calculation package that belong in the browser bundle.

    Returns:
        Sorted paths of the Python modules and JSON tables, without caches.
    """
    package = ROOT / "phasecore"
    return sorted(
        path
        for path in package.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix in {".py", ".json"}
    )


def write_phasecore_zip(target: Path) -> None:
    """
    Zip the calculation package so Pyodide can unpack it.

    Args:
        target: Destination ``phasecore.zip``.
    """
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in phasecore_files():
            info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def build(out_dir: Path) -> List[str]:
    """
    Write the static edition into a folder.

    Args:
        out_dir: Output folder. Existing generated files are replaced; the ``data``
            subfolder is left alone.

    Returns:
        Warnings for the user (for example when the data files are missing).
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "index.html").write_text(render_index(), encoding="utf-8", newline="\n")

    static_target = out_dir / "static"
    if static_target.exists():
        shutil.rmtree(static_target)
    shutil.copytree(ROOT / "static", static_target)

    vendor_dir = out_dir / "vendor"
    vendor_dir.mkdir(exist_ok=True)
    shutil.copyfile(Path(plotly.__file__).parent / "package_data" / "plotly.min.js", vendor_dir / "plotly.min.js")

    write_phasecore_zip(out_dir / "phasecore.zip")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    warnings: List[str] = []
    if not (out_dir / "data" / "manifest.json").exists():
        warnings.append(
            f"{out_dir / 'data'} has no manifest.json yet. Download the data first: "
            "python -m scripts.build_static_data --key-file <file> --elements Al,Fe,O"
        )
    return warnings


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    Command line entry point.

    Args:
        argv: Arguments; defaults to ``sys.argv[1:]``.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="static_site", help="Output folder (default: static_site).")
    args = parser.parse_args(argv)

    for message in build(Path(args.out)):
        print(f"warning: {message}")
    print(f"static edition written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
