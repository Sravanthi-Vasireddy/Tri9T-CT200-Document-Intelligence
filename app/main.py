import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, status, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db, init_db
from app.api import router as api_router
from app.schemas import HealthResponse

logger = logging.getLogger("doc_intelligence")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema on application startup
    try:
        init_db()
    except Exception as e:
        logger.error(f"Database initialization error on startup: {e}")
    yield


app = FastAPI(
    title="Tri9T-CT200-Document-Intelligence API",
    version="1.0.0",
    description="Backend Document Intelligence, Version Management, and QA Test Generation Engine for CardioTrack CT-200 Technical Documentation.",
    lifespan=lifespan
)

# Enable CORS for frontend / external integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Safe Exception Handler (protects internal database details & stack traces)
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"Internal database error processing {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database error occurred while processing the request. Contact system administrator."}
    )


# ---------------------------------------------------------
# 1. Health Check Endpoint
# ---------------------------------------------------------
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check verifying application status and database connectivity"
)
def health_check(db: Session = Depends(get_db)):
    try:
        # Verify active database connectivity
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"Health check database ping failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "app_name": "Tri9T-CT200-Document-Intelligence"
            }
        )

    return HealthResponse(
        status="healthy",
        database=db_status,
        app_name="Tri9T-CT200-Document-Intelligence"
    )


# Include API Routers
app.include_router(api_router)
