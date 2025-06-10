from typing import List
from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
import json

from .utils import make_phase_diagram_plotly, _hash_key
from .rate_limit import check_limit

app = FastAPI(title="PhaseNavigator")

# Serve /static (logoなど)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"❌ Validation Error:")
    print(f"  📍 URL: {request.url}")
    print(f"  📋 Method: {request.method}")
    print(f"  🔍 Headers: {dict(request.headers)}")
    
    try:
        body = await request.body()
        print(f"  📄 Body: {body.decode()}")
    except:
        print(f"  📄 Body: Could not decode body")
    
    print(f"  ❌ Errors: {exc.errors()}")
    return JSONResponse(
        status_code=400,
        content={"detail": f"Validation error: {exc.errors()}"}
    )


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
    e_cut: float = Form(0.2),  # デフォルト値を0.2に設定
    functional: str = Form("GGA_GGA_U_R2SCAN"),  # デフォルト汎関数
):
    # 温度値の変換処理
    try:
        temp_int = int(temp) if temp.strip() else 0
    except ValueError:
        temp_int = 0

    chems = [c.strip() for c in formulas.split(",") if c.strip()]
    if len(chems) < 2:
        raise HTTPException(status_code=400, detail="Please enter at least 2 chemical formulas separated by commas.")
    return templates.TemplateResponse(
        "index.html",
        {
            "request": req,
            "formulas": ",".join(chems),
            "temp": temp_int,
            "e_cut": e_cut,
            "functional": functional,
        },
    )


class DiagramRequest(BaseModel):
    f: List[str]
    temp: int
    e_cut: float
    functional: str


@app.post("/diagram/raw", response_class=JSONResponse)
def diagram_raw(
    payload: DiagramRequest,
    x_api_key: str = Header(..., alias="X-API-KEY"),
    ip: str = Depends(client_ip),
):
    print(f"🚀 API Request received:")
    print(f"  📊 Formulas: {payload.f}")
    print(f"  🌡️ Temperature: {payload.temp}")
    print(f"  ⚡ E_cut: {payload.e_cut}")
    print(f"  🔬 Functional: {payload.functional}")
    print(f"  🔑 API key length: {len(x_api_key)}")
    print(f"  🌐 Client IP: {ip}")
    
    if not check_limit((_hash_key(x_api_key), ip)):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait 30 seconds before making another request.")
    
    try:
        return make_phase_diagram_plotly(
            payload.f, payload.temp, x_api_key, ip, e_cut=payload.e_cut, functional=payload.functional
        )
    except Exception as e:
        print(f"❌ Error in make_phase_diagram_plotly: {str(e)}")
        error_msg = str(e)
        
        # Check for Materials Project API errors
        if "Invalid authentication credentials" in error_msg:
            raise HTTPException(status_code=401, detail="Invalid API key. Please check your Materials Project API key.")
        elif "REST query returned with error status code 401" in error_msg:
            raise HTTPException(status_code=401, detail="Invalid API key. Please check your Materials Project API key.")
        else:
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")