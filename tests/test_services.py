import re
import pytest
from unittest.mock import Mock, patch
from app.services.materials_client import MaterialsProjectClient
from app.services.rate_limiter import RateLimiter
from app.core.security import hash_api_key, validate_api_key


def test_hash_api_key():
    """Test API key hashing."""
    api_key = "test_api_key_32_characters_long!"
    hashed = hash_api_key(api_key)
    assert len(hashed) == 12
    assert isinstance(hashed, str)
    
    # Same key should produce same hash
    hashed2 = hash_api_key(api_key)
    assert hashed == hashed2


def test_validate_api_key():
    """Test API key validation."""
    # Valid key
    valid_key = "abcdefghijklmnopqrstuvwxyz123456"
    assert validate_api_key(valid_key) == True
    
    # Invalid keys
    assert validate_api_key("") == False
    assert validate_api_key("short") == False
    assert validate_api_key("toolongandcontainsinvalidcharacters!") == False
    assert validate_api_key(None) == False


def test_materials_client_elements_extraction():
    """Test element extraction from formulas."""
    client = MaterialsProjectClient("dummy_key")
    
    formulas = ["Fe2O3", "Al2O3", "SiO2"]
    elements = client.get_elements_from_formulas(formulas)
    
    assert set(elements) == {"Fe", "O", "Al", "Si"}
    assert elements == sorted(elements)  # Should be sorted


def test_materials_client_functional_mapping():
    """Test functional mapping."""
    client = MaterialsProjectClient("dummy_key")
    
    # Valid functionals
    # One joint thermo type: separate GGA and R2SCAN types would duplicate materials.
    assert client.get_functional_mapping("GGA_GGA_U_R2SCAN") == ["GGA_GGA+U_R2SCAN"]
    assert client.get_functional_mapping("R2SCAN") == ["R2SCAN"]
    assert client.get_functional_mapping("GGA_GGA_U") == ["GGA_GGA+U"]
    
    # Invalid functional
    with pytest.raises(ValueError):
        client.get_functional_mapping("INVALID")


def test_rate_limiter():
    """Test rate limiter functionality."""
    limiter = RateLimiter(window_seconds=10, max_requests=3)
    
    key = ("test_hash", "127.0.0.1")
    
    # Should allow first 3 requests
    assert limiter.is_allowed(key) == True
    assert limiter.is_allowed(key) == True
    assert limiter.is_allowed(key) == True
    
    # Should block 4th request
    assert limiter.is_allowed(key) == False
    
    # Check remaining requests
    assert limiter.get_remaining_requests(key) == 0

def _build_offline_entries():
    """Create a small Fe-Al-O set of computed entries without network access."""
    from pymatgen.core import Composition
    from pymatgen.entries.computed_entries import ComputedEntry

    data = [
        ("Fe", -8.3), ("Al", -3.7), ("O", -4.9),
        ("Fe2O3", -38.0), ("Al2O3", -37.5), ("FeAl2O4", -50.0),
    ]
    return [
        ComputedEntry(Composition(formula), energy, entry_id=f"mp-{i}")
        for i, (formula, energy) in enumerate(data)
    ]


def test_generated_plot_uses_formulas_not_dummy_species():
    """Axis labels show the entered formulas instead of dummy symbols like Xg0+."""
    import json
    from app.services.phase_analyzer import PhaseAnalyzer

    client = Mock()
    client.get_elements_from_formulas.return_value = ["Al", "Fe", "O"]
    client.fetch_entries.return_value = (_build_offline_entries(), 0)

    result = PhaseAnalyzer(client).generate_phase_diagram(
        formulas=["Fe2O3", "Al2O3"],
        temperature=0,
        energy_cutoff=0.2,
        functional="GGA_GGA_U",
        api_key="unused",
    )

    plot_json = json.dumps(result.plot)
    assert "Al2O3" in plot_json
    assert not re.search(r"\bX[a-z]\d?\+", plot_json)


def test_replace_dummy_labels_is_recursive():
    """Replacement reaches nested strings and keeps non-string values."""
    from app.services.phase_analyzer import replace_dummy_labels

    data = {"a": ["Fraction Xg0+", 1, None], "b": {"c": "Xf0+ and Xg0+"}}
    result = replace_dummy_labels(data, {"Xf0+": "Fe2O3", "Xg0+": "Al2O3"})
    assert result == {
        "a": ["Fraction Al2O3", 1, None],
        "b": {"c": "Fe2O3 and Al2O3"},
    }


# ---------- Non-commercial (CC BY-NC) data handling ----------

@pytest.mark.parametrize("entry_id, expected", [
    ("mp-1143-r2SCAN", "mp-1143"),
    ("mp-31770-GGA+U", "mp-31770"),
    ("mp-776475-GGA", "mp-776475"),
    ("mp-3222016", "mp-3222016"),
    ("mvc-12345-r2SCAN", "mvc-12345"),
])
def test_base_material_id_strips_functional_suffix(entry_id, expected):
    """The functional suffix is removed so IDs match Materials Project documents."""
    from app.services.materials_client import base_material_id

    assert base_material_id(entry_id) == expected


def test_subsystem_chemsys_lists_all_subsystems():
    """Every non-empty element subset is returned, sorted."""
    from app.services.materials_client import subsystem_chemsys

    assert sorted(subsystem_chemsys(["O", "Fe"])) == ["Fe", "Fe-O", "O"]
    assert len(subsystem_chemsys(["A", "B", "C", "D"])) == 15


def _license_doc(material_id, license_name, batch_id=None):
    """Build a fake summary document carrying builder_meta."""
    doc = Mock()
    doc.material_id = material_id
    doc.builder_meta = Mock(license=license_name, batch_id=batch_id)
    return doc


def _client_with_mock_mp(entries, license_docs=None, license_error=None):
    """Return a MaterialsProjectClient whose MPRester is replaced by a mock."""
    from pymatgen.core import Composition
    from pymatgen.entries.computed_entries import ComputedEntry

    built = [
        ComputedEntry(Composition(formula), -5.0, entry_id=entry_id)
        for formula, entry_id in entries
    ]
    mp = Mock()
    mp.__enter__ = Mock(return_value=mp)
    mp.__exit__ = Mock(return_value=False)
    mp.get_entries_in_chemsys.return_value = built
    if license_error is not None:
        mp.materials.search.side_effect = license_error
    else:
        mp.materials.search.return_value = license_docs or []
    client = MaterialsProjectClient("dummy_key")
    client._client = mp
    return client, mp


ENTRIES = [("Fe", "mp-1-GGA"), ("O", "mp-2-GGA"), ("Fe2O3", "mp-3-r2SCAN"), ("FeO", "mp-4-r2SCAN")]


def test_fetch_entries_excludes_non_commercial_by_default():
    """BY-NC and GNoME materials are removed and counted."""
    docs = [
        _license_doc("mp-3", "BY-NC", "gnome_r2scan_statics"),
        _license_doc("mp-4", "BY-C"),
    ]
    client, _ = _client_with_mock_mp(ENTRIES, docs)

    entries, excluded = client.fetch_entries(["Fe", "O"], 0, "R2SCAN")

    assert excluded == 1
    assert {str(e.entry_id) for e in entries} == {"mp-1-GGA", "mp-2-GGA", "mp-4-r2SCAN"}


def test_fetch_entries_can_include_non_commercial():
    """With the opt-in flag nothing is removed and no license lookup is made."""
    client, mp = _client_with_mock_mp(ENTRIES, [_license_doc("mp-3", "BY-NC")])

    entries, excluded = client.fetch_entries(["Fe", "O"], 0, "R2SCAN", include_non_commercial=True)

    assert excluded == 0
    assert len(entries) == 4
    mp.materials.search.assert_not_called()


def test_fetch_entries_fails_closed_when_license_lookup_fails():
    """If licenses cannot be checked, the request fails instead of returning unchecked data."""
    client, _ = _client_with_mock_mp(ENTRIES, license_error=RuntimeError("boom"))

    with pytest.raises(ValueError, match="Could not verify data licenses"):
        client.fetch_entries(["Fe", "O"], 0, "R2SCAN")


def test_fetch_entries_filters_before_gibbs_conversion():
    """Licenses are filtered on the 0 K entries, then only the kept ones become Gibbs entries."""
    from unittest.mock import patch

    docs = [_license_doc("mp-3", "BY-NC")]
    client, mp = _client_with_mock_mp(ENTRIES, docs)

    with patch("app.services.materials_client.GibbsComputedStructureEntry") as gibbs:
        gibbs.from_entries.side_effect = lambda entries, temp: list(entries)
        entries, excluded = client.fetch_entries(["Fe", "O"], 1000, "R2SCAN")

    assert excluded == 1
    assert "use_gibbs" not in mp.get_entries_in_chemsys.call_args.kwargs
    passed = gibbs.from_entries.call_args.args[0]
    assert {str(e.entry_id) for e in passed} == {"mp-1-GGA", "mp-2-GGA", "mp-4-r2SCAN"}
    assert gibbs.from_entries.call_args.kwargs["temp"] == 1000
    assert len(entries) == 3


def test_fetch_entries_rejects_elements_without_finite_temperature_data():
    """Elements missing from pymatgen's Gibbs table give a clear error before any request."""
    client, mp = _client_with_mock_mp(ENTRIES, [])

    with pytest.raises(ValueError, match="Finite-temperature data is not available for Ac"):
        client.fetch_entries(["Ac", "Fe"], 1000, "R2SCAN")

    mp.get_entries_in_chemsys.assert_not_called()
    # 0 K does not use the table, so the same elements are accepted there.
    client.fetch_entries(["Ac", "Fe"], 0, "R2SCAN", include_non_commercial=True)


def test_missing_terminal_after_exclusion_gives_clear_error():
    """If the only entry of a terminal formula was non-commercial, say so."""
    from app.services.phase_analyzer import PhaseAnalyzer

    client = Mock()
    client.get_elements_from_formulas.return_value = ["Al", "Fe", "O"]
    entries = [e for e in _build_offline_entries() if e.composition.reduced_formula != "Al2O3"]
    client.fetch_entries.return_value = (entries, 1)

    with pytest.raises(ValueError, match="No CC BY 4.0 entry found for 'Al2O3'"):
        PhaseAnalyzer(client).generate_phase_diagram(
            formulas=["Fe2O3", "Al2O3"], temperature=0, energy_cutoff=0.2,
            functional="GGA_GGA_U", api_key="unused",
        )


def test_metadata_reports_license_filtering():
    """The response says how many non-commercial entries were excluded."""
    from app.services.phase_analyzer import PhaseAnalyzer

    client = Mock()
    client.get_elements_from_formulas.return_value = ["Al", "Fe", "O"]
    client.fetch_entries.return_value = (_build_offline_entries(), 3)

    result = PhaseAnalyzer(client).generate_phase_diagram(
        formulas=["Fe2O3", "Al2O3"], temperature=0, energy_cutoff=0.2,
        functional="GGA_GGA_U", api_key="unused",
    )

    assert result.metadata.excluded_non_commercial == 3
    assert result.metadata.include_non_commercial is False
