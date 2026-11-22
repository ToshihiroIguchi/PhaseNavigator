from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from datetime import datetime, timezone
from pathlib import Path
import asyncio

import plotly
from plotly.offline import get_plotlyjs_version
from contextlib import asynccontextmanager

from .core.config import settings
from .core.errors import format_validation_errors
from .core.logging import setup_logging, get_logger
from .models.requests import FormDiagramRequest
from .models.responses import ErrorResponse
from .api.diagrams import router as diagrams_router
from .api.health import router as health_router

# Setup logging
logger = setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    
    # Start background task to clear expired rate limits periodically (every 10 minutes)
    async def clear_rate_limits_periodically():
        from .services.rate_limiter import rate_limiter
        try:
            while True:
                await asyncio.sleep(600)  # 10 minutes
                rate_limiter.clear_expired()
        except asyncio.CancelledError:
            logger.info("Rate limit cleanup background task cancelled")
        except Exception as e:
            logger.error(f"Error in rate limit cleanup background task: {e}")

    cleanup_task = asyncio.create_task(clear_rate_limits_periodically())
    
    yield
    
    # Cancel the background task on shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info(f"Shutting down {settings.app_name}")

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Phase diagram generation and analysis tool using Materials Project data",
    debug=settings.debug,
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Plotly.js bundled with the installed plotly package. Serving it locally keeps
# the browser bundle in lockstep with the figures produced by the Python side.
PLOTLY_JS_PATH = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
templates.env.globals["plotly_js_version"] = get_plotlyjs_version()
templates.env.globals["app_version"] = settings.app_version
# Asset locations are variables so the static edition (scripts/build_static_site.py)
# can render the same templates with relative paths.
templates.env.globals["static_edition"] = False
templates.env.globals["static_prefix"] = "/static"
templates.env.globals["vendor_prefix"] = "/vendor"

# Include API routers
app.include_router(diagrams_router, prefix="/api")
app.include_router(health_router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed logging."""
    logger.error(f"Validation Error - URL: {request.url}, Method: {request.method}")
    logger.error(f"Validation errors: {exc.errors()}")
    
    try:
        body = await request.body()
        logger.error(f"Request body: {body.decode()}")
    except Exception:
        logger.error("Could not decode request body")
    
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            detail=format_validation_errors(exc.errors()),
            error_code="VALIDATION_ERROR",
            timestamp=datetime.now(timezone.utc).isoformat()
        ).model_dump()
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent error format."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=exc.detail,
            error_code="HTTP_ERROR",
            timestamp=datetime.now(timezone.utc).isoformat()
        ).model_dump(),
        headers=getattr(exc, 'headers', None)
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            detail="Internal server error",
            error_code="INTERNAL_ERROR",
            timestamp=datetime.now(timezone.utc).isoformat()
        ).model_dump()
    )


@app.get("/vendor/plotly.min.js", include_in_schema=False)
async def plotly_js():
    """
    Serve the plotly.js bundle shipped with the Python plotly package.

    Returns:
        The JavaScript file with a long cache lifetime (the page URL carries
        the version, so a new version is fetched automatically).
    """
    return FileResponse(
        PLOTLY_JS_PATH,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=86400"}
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main application page."""
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/diagram", response_class=HTMLResponse)
async def diagram_form(
    request: Request,
    formulas: str = Form(...),
    temp: str = Form("0"),
    e_cut: float = Form(settings.default_energy_cutoff),
    functional: str = Form(settings.default_functional),
    include_non_commercial: bool = Form(False),
):
    """
    Handle form-based diagram requests (for HTML form compatibility).
    
    This endpoint processes form data and renders the page with the provided parameters.
    The actual diagram generation is handled by the JavaScript frontend calling the API.
    """
    try:
        # Validate form data
        form_request = FormDiagramRequest(
            formulas=formulas,
            temp=temp,
            e_cut=e_cut,
            functional=functional,
            include_non_commercial=include_non_commercial
        )
        
        # Convert to API request format for validation
        api_request = form_request.to_diagram_request()
        
        # Render template with validated parameters
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "formulas": ",".join(api_request.formulas),
                "temp": api_request.temperature,
                "e_cut": api_request.energy_cutoff,
                "functional": api_request.functional,
            }
        )
        
    except ValueError as e:
        logger.warning(f"Form validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))





if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )