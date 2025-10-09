"""FastAPI main application."""

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time

from app.config import settings
from app.exceptions import (
    CatenException,
    caten_exception_handler,
    general_exception_handler,
    http_exception_handler
)
from app.routes import v1_api, v2_api, health
from app.services.rate_limiter import rate_limiter

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration', ['method', 'endpoint'])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    logger.info("Starting Caten API server", version="1.0.0")
    yield
    logger.info("Shutting down Caten API server")
    await rate_limiter.close()


# Create FastAPI application
app = FastAPI(
    title="Caten API",
    description="FastAPI backend for text and image processing with LLM integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "X-CSRFToken",
        "X-Forwarded-For",
        "User-Agent",
        "Origin",
        "Referer",
        "Cache-Control",
        "Pragma",
        "Content-Disposition",
        "Content-Transfer-Encoding",
        "X-File-Name",
        "X-File-Size",
        "X-File-Type"
    ],
    expose_headers=[
        "Content-Length",
        "Content-Type",
        "Cache-Control",
        "X-Accel-Buffering",
        "Content-Disposition",
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Methods",
        "Access-Control-Allow-Headers"
    ],
    max_age=3600,  # Cache preflight response for 1 hour
)


@app.middleware("http")
async def cors_preflight_handler(request: Request, call_next):
    """Handle CORS preflight requests explicitly for Chrome extensions and file uploads."""
    if request.method == "OPTIONS":
        response = Response()
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "Accept, Accept-Language, Content-Language, Content-Type, Authorization, X-Requested-With, X-CSRFToken, X-Forwarded-For, User-Agent, Origin, Referer, Cache-Control, Pragma, Content-Disposition, Content-Transfer-Encoding, X-File-Name, X-File-Size, X-File-Type"
        response.headers["Access-Control-Max-Age"] = "3600"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Expose-Headers"] = "Content-Length, Content-Type, Cache-Control, X-Accel-Buffering, Content-Disposition, Access-Control-Allow-Origin, Access-Control-Allow-Methods, Access-Control-Allow-Headers"
        return response
    
    response = await call_next(request)
    
    # Add CORS headers to all responses
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Expose-Headers"] = "Content-Length, Content-Type, Cache-Control, X-Accel-Buffering, Content-Disposition, Access-Control-Allow-Origin, Access-Control-Allow-Methods, Access-Control-Allow-Headers"
    
    return response


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Logging and metrics middleware."""
    start_time = time.time()
    
    # Log request
    logger.info(
        "HTTP request started",
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host
    )
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Update metrics
    if settings.enable_metrics:
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
    
    # Log response
    logger.info(
        "HTTP request completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration=f"{duration:.3f}s"
    )
    
    return response


# Add exception handlers
app.add_exception_handler(CatenException, caten_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include routers
app.include_router(health.router)
app.include_router(v1_api.router)
app.include_router(v2_api.router)


@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint."""
    if not settings.enable_metrics:
        return Response("Metrics disabled", status_code=404)
    
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint that redirects to docs."""
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
