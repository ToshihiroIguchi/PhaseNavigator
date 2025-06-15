from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from datetime import datetime

from .core.config import settings
from .core.logging import setup_logging, get_logger
from .models.requests import FormDiagramRequest
from .models.responses import ErrorResponse
from .api.diagrams import router as diagrams_router
from .api.health import router as health_router

# Setup logging
logger = setup_logging()

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Phase diagram generation and analysis tool using Materials Project data",
    debug=settings.debug
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

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
            detail=f"Validation error: {exc.errors()}",
            error_code="VALIDATION_ERROR",
            timestamp=datetime.utcnow().isoformat()
        ).dict()
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent error format."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=exc.detail,
            error_code="HTTP_ERROR",
            timestamp=datetime.utcnow().isoformat()
        ).dict(),
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
            timestamp=datetime.utcnow().isoformat()
        ).dict()
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main application page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/diagram", response_class=HTMLResponse)
async def diagram_form(
    request: Request,
    formulas: str = Form(...),
    temp: str = Form("0"),
    e_cut: float = Form(settings.default_energy_cutoff),
    functional: str = Form(settings.default_functional),
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
            functional=functional
        )
        
        # Convert to API request format for validation
        api_request = form_request.to_diagram_request()
        
        # Render template with validated parameters
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "formulas": ",".join(api_request.formulas),
                "temp": api_request.temperature,
                "e_cut": api_request.energy_cutoff,
                "functional": api_request.functional,
            }
        )
        
    except ValueError as e:
        logger.warning(f"Form validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info(f"Shutting down {settings.app_name}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )