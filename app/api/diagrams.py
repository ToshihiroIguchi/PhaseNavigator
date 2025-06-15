from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from ..core.logging import get_logger
from ..core.security import hash_api_key, create_rate_limit_key, validate_api_key
from ..models.requests import DiagramRequest
from ..models.responses import DiagramResponse, ErrorResponse
from ..services.materials_client import MaterialsProjectClient
from ..services.phase_analyzer import PhaseAnalyzer
from ..services.rate_limiter import rate_limiter

logger = get_logger(__name__)
router = APIRouter(prefix="/diagrams", tags=["diagrams"])


def get_client_ip(request: Request) -> str:
    """Extract client IP from request (proxy-aware)."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host or "unknown"


@router.post("/", response_model=DiagramResponse)
async def generate_diagram(
    request: DiagramRequest,
    x_api_key: str = Header(..., alias="X-API-KEY"),
    client_ip: str = Depends(get_client_ip)
):
    """
    Generate a phase diagram with detailed phase information.
    
    This endpoint creates a phase diagram using Materials Project data
    and returns both the plot data and detailed phase information.
    """
    # Validate API key format
    if not validate_api_key(x_api_key):
        logger.warning(f"Invalid API key format from IP: {client_ip}")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key format"
        )
    
    # Create rate limiting key
    api_key_hash = hash_api_key(x_api_key)
    rate_limit_key = create_rate_limit_key(api_key_hash, client_ip)
    
    # Check rate limit
    if not rate_limiter.is_allowed(rate_limit_key):
        remaining_time = rate_limiter.get_reset_time(rate_limit_key) - __import__('time').time()
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Please wait {int(remaining_time)} seconds before making another request.",
            headers={"Retry-After": str(int(remaining_time))}
        )
    
    # Log request details
    logger.info(f"API Request: formulas={request.formulas}, T={request.temperature}K, "
               f"e_cut={request.energy_cutoff}, functional={request.functional}, "
               f"key_hash={api_key_hash}, IP={client_ip}")
    
    try:
        # Create services
        materials_client = MaterialsProjectClient(x_api_key)
        phase_analyzer = PhaseAnalyzer(materials_client)
        
        # Generate phase diagram
        result = phase_analyzer.generate_phase_diagram(
            formulas=request.formulas,
            temperature=request.temperature,
            energy_cutoff=request.energy_cutoff,
            functional=request.functional,
            api_key=x_api_key
        )
        
        logger.info(f"Diagram generated successfully: {len(result.phase_info)} phases")
        return result
        
    except ValueError as e:
        # Client errors (bad input, invalid API key, etc.)
        logger.warning(f"Client error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        # Server errors
        logger.error(f"Server error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while generating phase diagram"
        )