from typing import List
from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .utils import make_phase_diagram_plotly, _hash_key
from .rate_limit import check_limit

app = FastAPI(title="PhaseNavigator")

# Serve /static (logoなど)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def client_ip(req: Request) -> str:
    """クライアント IP（proxy 対応）"""
    fwd = req.headers.get("x-forwarded-for")
    return (fwd.split(",")[0] if fwd else req.client.host) or "unknown"


@app.get("/", response_class=HTMLResponse)
def index(req: Request):
    return templates.TemplateResponse("index.html", {"request": req})


@app.post("/diagram", response_class=HTMLResponse)
def diagram(
    req: Request,
    formulas: str = Form(...),
    temp: str = Form("0"),  # 文字列として受け取り
    e_cut: float = Form(...),
):
    # 温度値の変換処理
    try:
        temp_int = int(temp) if temp.strip() else 0
    except ValueError:
        temp_int = 0

    chems = [c.strip() for c in formulas.split(",") if c.strip()]
    if len(chems) < 2:
        raise HTTPException(status_code=400, detail="Enter ≥2 formulas")
    return templates.TemplateResponse(
        "index.html",
        {
            "request": req,
            "formulas": ",".join(chems),
            "temp": temp_int,
            "e_cut": e_cut,
        },
    )


class DiagramRequest(BaseModel):
    f: List[str]
    temp: int
    e_cut: float


@app.post("/diagram/raw", response_class=JSONResponse)
def diagram_raw(
    payload: DiagramRequest,
    x_api_key: str = Header(..., alias="X-API-KEY"),
    ip: str = Depends(client_ip),
):
    if not check_limit((_hash_key(x_api_key), ip)):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return make_phase_diagram_plotly(
        payload.f, payload.temp, x_api_key, ip, e_cut=payload.e_cut
    )