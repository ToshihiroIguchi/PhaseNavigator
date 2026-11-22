"""Tests for the static data tooling: record conversion, license filtering and file output."""
import gzip
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pymatgen.analysis.compatibility.computed_entries import G_ELEMS, G_GASES

from phasecore import tables
from phasecore.entries import RECORD_FIELDS, Dataset, Entry
from scripts import build_static_data as build
from scripts.export_reference_tables import atomic_masses
from tests.phasecore_data import SPECS, make_entries


def test_reference_tables_match_pymatgen():
    """The bundled copies equal what the installed pymatgen ships."""
    assert tables.G_ELEMS == G_ELEMS
    assert tables.G_GASES == G_GASES
    assert tables.ATOMIC_MASSES == pytest.approx(atomic_masses())


def test_record_layout_and_values():
    """A record carries the fields the core needs, with gas data flagged."""
    entries = {str(e.entry_id): e for e in make_entries()}
    record = dict(zip(RECORD_FIELDS, build.entry_to_record(entries["mp-20-GGA"])))

    assert record["entry_id"] == "mp-20-GGA"
    assert record["composition"] == {"C": 4, "O": 8}
    assert record["formula"] == "CO2"
    assert record["gas_formula"] == "CO2"
    assert record["gas_factor"] == 4.0
    assert record["energy"] == pytest.approx(entries["mp-20-GGA"].energy, abs=1e-8)
    assert record["correction"] == pytest.approx(entries["mp-20-GGA"].correction, abs=1e-8)

    solid = dict(zip(RECORD_FIELDS, build.entry_to_record(entries["mp-10-GGA+U"])))
    assert solid["gas_formula"] is None and solid["gas_factor"] is None
    assert solid["formula"] == "Fe2O3"


def test_entry_composition_string_keeps_structure_order():
    """The composition text uses the stored element order, like pymatgen."""
    entries = {str(e.entry_id): e for e in make_entries()}
    for spec in SPECS:
        entry = entries[spec[0]]
        own = Entry.from_record(build.entry_to_record(entry))
        assert own.composition_string == str(entry.composition)


@pytest.mark.parametrize(
    "license_name,batch_id,expected",
    [
        ("BY-C", None, True),
        ("BY-C", "other_batch", True),
        ("BY-NC", None, False),
        ("BY-C", "gnome_r2scan_statics", False),
        (None, None, False),
        ("SOMETHING-NEW", None, False),
    ],
)
def test_only_known_cc_by_licenses_are_redistributable(license_name, batch_id, expected):
    """Unknown or missing licenses are excluded (fail closed)."""
    assert build.is_redistributable(license_name, batch_id) is expected


def test_subsystem_chemsys_is_sorted_and_complete():
    """All 7 subsystems of a ternary are listed with sorted element names."""
    assert build.subsystem_chemsys(["O", "Fe", "Al"]) == ["Al", "Fe", "O", "Al-Fe", "Al-O", "Fe-O", "Al-Fe-O"]


def _fake_client(entries, licenses):
    """Build a mock MPRester over synthetic entries and a {material_id: (license, batch)} map."""
    by_material = {str(e.entry_id).rsplit("-", 1)[0]: e for e in entries}
    client = Mock()
    client.materials.search.return_value = [
        SimpleNamespace(material_id=mid, builder_meta=SimpleNamespace(license=lic, batch_id=batch))
        for mid, (lic, batch) in licenses.items()
    ]
    client.materials.thermo.search.return_value = [SimpleNamespace(material_id=mid) for mid in by_material]
    client.get_entries.side_effect = lambda ids, additional_criteria: [by_material[i] for i in ids]
    return client


def test_build_dataset_drops_non_commercial_and_unknown_licenses():
    """GNoME, BY-NC and unlabeled materials never reach the dataset."""
    entries = make_entries()[:6]
    licenses = {f"mp-{i}": ("BY-C", None) for i in range(1, 7)}
    licenses["mp-2"] = ("BY-NC", "gnome_r2scan_statics")
    licenses["mp-3"] = ("BY-NC", None)
    del licenses["mp-4"]  # no license information at all

    payload = build.build_dataset(_fake_client(entries, licenses), "GGA_GGA_U", None, log=lambda *_: None)

    ids = [record[0] for record in payload["entries"]]
    assert ids == ["mp-1-GGA", "mp-5-GGA", "mp-6-GGA"]
    assert payload["excluded_by_license"] == 3
    assert payload["count"] == 3
    assert payload["license"] == "CC BY 4.0"
    assert payload["fields"] == list(RECORD_FIELDS)


def test_written_dataset_is_reproducible_and_loadable(tmp_path):
    """The same payload gives the same bytes, and the file loads back into a Dataset."""
    entries = make_entries()
    licenses = {str(e.entry_id).rsplit("-", 1)[0]: ("BY-C", None) for e in entries}
    payload = build.build_dataset(_fake_client(entries, licenses), "GGA_GGA_U", None, log=lambda *_: None)

    first = build.write_gzip_json(tmp_path / "a.json.gz", payload)
    second = build.write_gzip_json(tmp_path / "b.json.gz", payload)
    dataset = Dataset.from_json(gzip.decompress((tmp_path / "a.json.gz").read_bytes()).decode("utf-8"))

    assert first == second
    assert len(dataset) == len(entries)
    assert {e.entry_id for e in dataset.select(["Fe", "O"])} >= {"mp-1-GGA", "mp-10-GGA+U"}
    assert all(e.elements <= {"Fe", "O"} for e in dataset.select(["Fe", "O"]))


def test_dataset_rejects_other_schemas_and_layouts():
    """A file written for another version of the core is refused with a clear message."""
    with pytest.raises(ValueError, match="Unsupported dataset schema"):
        Dataset.from_json(json.dumps({"schema": 99, "fields": list(RECORD_FIELDS), "entries": []}))
    with pytest.raises(ValueError, match="record layout"):
        Dataset.from_json(json.dumps({"schema": 1, "fields": ["entry_id"], "entries": []}))


def test_key_is_read_from_file_or_environment(tmp_path, monkeypatch):
    """The key comes from a file or MP_API_KEY and a missing key stops the script."""
    key_file = tmp_path / "key.txt"
    key_file.write_text("  abc123\n", encoding="utf-8")
    assert build.read_key(str(key_file)) == "abc123"

    monkeypatch.setenv("MP_API_KEY", "fromenv")
    assert build.read_key(None) == "fromenv"

    monkeypatch.delenv("MP_API_KEY")
    with pytest.raises(SystemExit):
        build.read_key(None)
