import hashlib, json, logging
from typing import List

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from mp_api.client import MPRester
from pymatgen.analysis.phase_diagram import CompoundPhaseDiagram, PDPlotter
from pymatgen.core.composition import Composition

# ─────────── logging ───────────
logger = logging.getLogger("phasenav")
fh = logging.FileHandler("phasenav.log")
fh.setFormatter(logging.Formatter("%(asctime)s  %(message)s"))
logger.addHandler(fh)
logger.setLevel(logging.INFO)
# ───────────────────────────────

def _elements(flist: List[str]) -> List[str]:
    """Return sorted unique element symbols in formulas."""
    return sorted({el.symbol for f in flist for el in Composition(f)})

def _hash_key(key: str) -> str:
    """Short SHA‐256 digest of API key."""
    return hashlib.sha256(key.encode()).hexdigest()[:12]

def make_phase_diagram_plotly(
    formulas: List[str],
    temp: int,
    api_key: str,
    ip: str,
    e_cut: float,
    functional: str = "GGA_GGA_U_R2SCAN",
) -> JSONResponse:

    # ─── validation ───────────────────────────────────────────
    if temp != 0 and not 300 <= temp <= 2000:
        raise HTTPException(status_code=400,
            detail="Temperature must be 0 K or between 300-2000 K. Please adjust the temperature setting.")
    if len(formulas) < 2:
        raise HTTPException(status_code=400, detail="At least 2 chemical formulas are required. Please add more formulas.")
    if len(formulas) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 formulas allowed. Please remove some formulas.")
    if e_cut < 0:
        raise HTTPException(status_code=400, detail="Energy cutoff must be greater than or equal to 0 eV/atom.")

    elements = _elements(formulas)

    # ─── functional mapping ─────────────────────────────────
    functional_map = {
        "GGA_GGA_U_R2SCAN": ["GGA_GGA+U", "R2SCAN"],
        "R2SCAN": ["R2SCAN"],
        "GGA_GGA_U": ["GGA_GGA+U"]
    }
    
    if functional not in functional_map:
        raise HTTPException(status_code=400, detail=f"Unsupported functional: {functional}. Supported: GGA_GGA_U_R2SCAN, R2SCAN, GGA_GGA_U")
    
    thermo_types = functional_map[functional]

    # ─── fetch Materials Project entries ─────────────────────
    with MPRester(api_key=api_key) as m:
        entries = (m.get_entries_in_chemsys(elements, additional_criteria={"thermo_types": thermo_types}) if temp == 0
                   else m.get_entries_in_chemsys(elements, use_gibbs=temp, additional_criteria={"thermo_types": thermo_types}))

    if not entries:
        raise HTTPException(status_code=404, detail=f"No materials found for elements {', '.join(elements)} in Materials Project database. Try different chemical formulas.")

    # ─── build phase diagram ─────────────────────────────────
    terminals = [Composition(f) for f in formulas[:len(formulas)]]
    pd = CompoundPhaseDiagram(entries, terminals, normalize_terminal_compositions=True)

    fig = PDPlotter(pd, backend="plotly", show_unstable=e_cut).get_plot()

    logger.info("PD  T=%dK  elems=%s  e_cut=%.3f  func=%s  keyHash=%s  ip=%s",
                temp, ",".join(elements), e_cut, functional, _hash_key(api_key), ip)

    return JSONResponse(content=json.loads(fig.to_json()))