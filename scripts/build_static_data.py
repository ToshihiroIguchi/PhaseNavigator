"""Download Materials Project entries once and store them for the static edition.

The static site cannot call the Materials Project API (that needs a key), so this
script fetches the data ahead of time and writes compact, gzip-compressed JSON files
that ``phasecore`` reads in the browser.

Only materials whose license is CC BY 4.0 are written. A material is dropped when its
license is anything else (including CC BY-NC, e.g. GNoME) or when the license cannot be
determined, so unknown cases fail closed.

The API key is read from the ``MP_API_KEY`` environment variable or from a key file
given with ``--key-file``; it is never printed or stored. Keep the key file outside the
repository.

Examples (run from the repository root with the project virtual environment's Python)::

    python -m scripts.build_static_data --key-file /path/to/key.txt --elements Al,Fe,O
    python -m scripts.build_static_data --key-file /path/to/key.txt --all

A full download covers about 150,000 to 180,000 entries per thermo type and takes a
long time; use ``--elements`` for a quick, small build. Materials Project also
publishes bulk data on AWS Open Data, which is the better source for a full build.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import itertools
import json
import os
import sys
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from phasecore.entries import RECORD_FIELDS, SCHEMA_VERSION

# Materials Project license labels (builder_meta.license) that may be redistributed
# under CC BY 4.0. Everything else, including "BY-NC", is excluded.
ALLOWED_LICENSES = frozenset({"BY-C"})

# Thermo types per UI functional, with the file each one is stored in.
DATASETS: Dict[str, Dict[str, str]] = {
    "GGA_GGA_U": {"thermo_type": "GGA_GGA+U", "file": "entries_gga_ggau.json.gz"},
    "GGA_GGA_U_R2SCAN": {"thermo_type": "GGA_GGA+U_R2SCAN", "file": "entries_gga_ggau_r2scan.json.gz"},
    "R2SCAN": {"thermo_type": "R2SCAN", "file": "entries_r2scan.json.gz"},
}

ID_BATCH_SIZE = 200
MAX_ELEMENTS_FOR_SUBSET_QUERY = 9


def _round(value: float, digits: int) -> float:
    """
    Round for compact storage.

    Args:
        value: Number to round.
        digits: Decimal places to keep.

    Returns:
        The rounded float.
    """
    return round(float(value), digits)


def entry_to_record(entry: Any) -> List[Any]:
    """
    Convert a pymatgen ``ComputedStructureEntry`` into a dataset record.

    Args:
        entry: An entry as returned by ``MPRester.get_entries``.

    Returns:
        A list laid out as ``phasecore.entries.RECORD_FIELDS``. The cell structure is
        reduced to its volume per atom; gas data is flagged when NIST-JANAF data
        would replace the entry at finite temperature.
    """
    from pymatgen.analysis.compatibility.computed_entries import G_GASES

    composition = {}
    for element, amount in entry.composition.items():
        amount = float(amount)
        composition[element.symbol] = int(amount) if amount.is_integer() else amount

    gas_formula: Optional[str] = None
    gas_factor: Optional[float] = None
    if not entry.composition.is_element:
        integer_formula, factor = entry.composition.get_integer_formula_and_factor()
        if integer_formula in G_GASES:
            gas_formula, gas_factor = integer_formula, float(factor)

    structure = entry.structure
    return [
        str(entry.entry_id),
        composition,
        _round(entry.energy, 8),
        _round(entry.correction, 8),
        _round(structure.volume / len(structure), 6),
        entry.composition.reduced_formula,
        gas_formula,
        gas_factor,
    ]


def is_redistributable(license_name: Optional[str], batch_id: Optional[str]) -> bool:
    """
    Decide whether a material's data may be included in the static dataset.

    Args:
        license_name: ``builder_meta.license`` of the material, if known.
        batch_id: ``builder_meta.batch_id`` of the material, if any.

    Returns:
        True only for a known CC BY license that is not a GNoME batch.
    """
    if license_name not in ALLOWED_LICENSES:
        return False
    return not str(batch_id or "").lower().startswith("gnome")


def subsystem_chemsys(elements: Sequence[str]) -> List[str]:
    """
    List every chemical subsystem of the given elements.

    Args:
        elements: Element symbols.

    Returns:
        Hyphen-joined, alphabetically sorted systems from single elements to the full set.
    """
    ordered = sorted(set(elements))
    return [
        "-".join(combo)
        for size in range(1, len(ordered) + 1)
        for combo in itertools.combinations(ordered, size)
    ]


# Largest number of elements in one Materials Project material (the query ranges up to this).
MAX_ELEMENTS_IN_MATERIAL = 9


def redistributable_ids(client: Any, chemsys: Optional[List[str]]) -> Set[str]:
    """
    Collect the IDs of materials that may be redistributed.

    Args:
        client: An open ``MPRester``.
        chemsys: Chemical systems to restrict to, or ``None`` for all materials.

    Returns:
        Material IDs with a known CC BY license.
    """
    queries: List[Dict[str, Any]]
    if chemsys:
        queries = [{"chemsys": chemsys}]
    else:
        # One request for the whole database fails in the client's bulk transfer, so split by the
        # number of elements. A failing request raises: a partial list would silently drop materials.
        queries = [{"num_elements": (n, n)} for n in range(1, MAX_ELEMENTS_IN_MATERIAL + 1)]
    allowed: Set[str] = set()
    for query in queries:
        for doc in client.materials.search(fields=["material_id", "builder_meta"], **query):
            meta = getattr(doc, "builder_meta", None)
            if is_redistributable(getattr(meta, "license", None), getattr(meta, "batch_id", None)):
                allowed.add(str(doc.material_id))
    return allowed


def thermo_ids(client: Any, thermo_type: str, chemsys: Optional[List[str]]) -> List[str]:
    """
    List the materials that have a thermo document of the given type.

    Args:
        client: An open ``MPRester``.
        thermo_type: e.g. ``"GGA_GGA+U_R2SCAN"``.
        chemsys: Chemical systems to restrict to, or ``None`` for all materials.

    Returns:
        Sorted material IDs.
    """
    kwargs: Dict[str, Any] = {"thermo_types": [thermo_type], "fields": ["material_id"], "all_fields": False}
    if chemsys:
        kwargs["chemsys"] = chemsys
    return sorted({str(doc.material_id) for doc in client.materials.thermo.search(**kwargs)})


def batched(items: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    """
    Split a sequence into chunks.

    Args:
        items: The sequence.
        size: Chunk length.

    Yields:
        Consecutive slices of ``items``.
    """
    for start in range(0, len(items), size):
        yield items[start:start + size]


def build_dataset(
    client: Any,
    functional: str,
    chemsys: Optional[List[str]],
    limit: Optional[int] = None,
    log: Any = print,
    scope: Any = "all",
    allowed: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Download and convert the entries of one thermo type.

    Args:
        client: An open ``MPRester``.
        functional: Key of ``DATASETS``.
        chemsys: Chemical systems to restrict to, or ``None`` for everything.
        limit: Stop after this many materials (for smoke tests).
        log: Function used for progress messages.
        scope: ``"all"`` or the list of elements the download covers.
        allowed: Redistributable IDs from ``redistributable_ids``; looked up when omitted
            (pass it to share one lookup between several thermo types).

    Returns:
        The dataset payload ready to be written as JSON.
    """
    thermo_type = DATASETS[functional]["thermo_type"]
    if allowed is None:
        allowed = redistributable_ids(client, chemsys)
    candidates = thermo_ids(client, thermo_type, chemsys)
    kept = [mid for mid in candidates if mid in allowed]
    excluded = len(candidates) - len(kept)
    if limit:
        kept = kept[:limit]
    log(f"{thermo_type}: {len(candidates)} materials, {excluded} excluded by license, fetching {len(kept)}")

    records: Dict[str, List[Any]] = {}
    for number, batch in enumerate(batched(kept, ID_BATCH_SIZE), start=1):
        entries = client.get_entries(list(batch), additional_criteria={"thermo_types": [thermo_type]})
        for entry in entries:
            records[str(entry.entry_id)] = entry_to_record(entry)
        if number % 10 == 0:
            log(f"  {min(number * ID_BATCH_SIZE, len(kept))}/{len(kept)} materials")

    return {
        "schema": SCHEMA_VERSION,
        "fields": list(RECORD_FIELDS),
        "thermo_type": thermo_type,
        "functional": functional,
        "license": "CC BY 4.0",
        "source": "Materials Project",
        "scope": scope,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(records),
        "excluded_by_license": excluded,
        "entries": [records[key] for key in sorted(records)],
    }


def write_gzip_json(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Write a payload as compact gzip-compressed JSON (reproducible bytes).

    Args:
        path: Destination file.
        payload: JSON-serializable content.

    Returns:
        ``{"bytes": ..., "sha256": ...}`` of the written file.
    """
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        # An empty filename keeps the gzip header free of the output path, so the same
        # payload always gives the same bytes.
        with gzip.GzipFile(filename="", fileobj=handle, mode="wb", mtime=0, compresslevel=9) as gz:
            gz.write(raw)
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def tool_versions() -> Dict[str, str]:
    """
    Record the versions of the libraries that produced the data.

    Returns:
        Mapping from package name to version, for the packages that are installed.
    """
    versions = {}
    for name in ("mp-api", "emmet-core", "pymatgen", "pymatgen-core"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pass
    return versions


def read_key(key_file: Optional[str]) -> str:
    """
    Read the API key without ever echoing it.

    Args:
        key_file: Optional path of a text file holding the key.

    Returns:
        The key.

    Raises:
        SystemExit: If no key is available.
    """
    if key_file:
        return Path(key_file).read_text(encoding="utf-8").strip()
    key = os.environ.get("MP_API_KEY", "").strip()
    if not key:
        raise SystemExit("Set MP_API_KEY or pass --key-file (keep the file outside the repository).")
    return key


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    Command line entry point.

    Args:
        argv: Arguments; defaults to ``sys.argv[1:]``.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--elements", help="Comma-separated elements; includes all their subsystems (max 9).")
    group.add_argument("--all", action="store_true", help="Download every material (very slow).")
    parser.add_argument("--out", default="static_site/data", help="Output directory.")
    parser.add_argument("--key-file", help="Text file holding the API key (outside the repository).")
    parser.add_argument(
        "--functionals", default=",".join(DATASETS), help="Comma-separated subset of: " + ", ".join(DATASETS)
    )
    parser.add_argument("--limit", type=int, help="Maximum materials per thermo type (smoke tests).")
    args = parser.parse_args(argv)

    chemsys: Optional[List[str]] = None
    scope: Any = "all"
    if args.elements:
        elements = sorted({e.strip() for e in args.elements.split(",") if e.strip()})
        if len(elements) > MAX_ELEMENTS_FOR_SUBSET_QUERY:
            raise SystemExit(f"--elements accepts at most {MAX_ELEMENTS_FOR_SUBSET_QUERY} elements; use --all.")
        chemsys = subsystem_chemsys(elements)
        scope = elements

    functionals = [f.strip() for f in args.functionals.split(",") if f.strip()]
    unknown = [f for f in functionals if f not in DATASETS]
    if unknown:
        raise SystemExit(f"Unknown functional(s): {', '.join(unknown)}")

    from mp_api.client import MPRester

    out_dir = Path(args.out)
    manifest: Dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "built_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope": scope,
        "tools": tool_versions(),
        "datasets": {},
    }
    with MPRester(api_key=read_key(args.key_file)) as client:
        try:
            manifest["database_version"] = client.get_database_version()
        except Exception:  # noqa: BLE001 - the version is informational only
            manifest["database_version"] = None
        allowed = redistributable_ids(client, chemsys)
        print(f"{len(allowed)} materials carry a redistributable license")
        for functional in functionals:
            payload = build_dataset(client, functional, chemsys, args.limit, scope=scope, allowed=allowed)
            payload["database_version"] = manifest["database_version"]
            info = write_gzip_json(out_dir / DATASETS[functional]["file"], payload)
            manifest["datasets"][functional] = {
                "thermo_type": payload["thermo_type"],
                "file": DATASETS[functional]["file"],
                "count": payload["count"],
                "excluded_by_license": payload["excluded_by_license"],
                **info,
            }
            print(f"wrote {DATASETS[functional]['file']}: {payload['count']} entries, {info['bytes']} bytes")

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
