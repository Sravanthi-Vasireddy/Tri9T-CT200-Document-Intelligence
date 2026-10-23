import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, status, Request
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db, init_db
from app.api import router as api_router
from app.schemas import HealthResponse
from app.swagger_theme import get_custom_swagger_css

logger = logging.getLogger("doc_intelligence")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema on application startup
    try:
        init_db()
        # Auto-seed CT-200 documents if running on a fresh/ephemeral database
        should_seed = os.getenv("AUTO_SEED_DOCUMENTS", "true").lower() in ("true", "1", "yes")
        if should_seed:
            from app.database import SessionLocal
            from app.models import DocumentVersion, Selection, SelectionItem, DocumentNodeModel
            with SessionLocal() as db:
                if db.query(DocumentVersion).count() == 0:
                    logger.info("Fresh database detected. Auto-ingesting CT-200 manuals (V1 and V2)...")
                    from app.ingestion import IngestionService
                    data_dir = Path(__file__).resolve().parent.parent / "data"
                    v1_pdf = data_dir / "ct200_manual.pdf"
                    v2_pdf = data_dir / "ct200_manual_v2.pdf"
                    if v1_pdf.exists():
                        IngestionService.ingest_pdf(str(v1_pdf), version_number="v1", document_id="ct200_manual", db=db)
                    if v2_pdf.exists():
                        IngestionService.ingest_pdf(str(v2_pdf), version_number="v2", document_id="ct200_manual", db=db)
                    logger.info("Auto-ingestion of CT-200 manuals completed successfully.")

                if db.query(Selection).count() == 0:
                    logger.info("Auto-seeding default CT-200 Core Baseline Requirements selection...")
                    target_node_ids = [
                        "v1_sec_1_1",
                        "v1_sec_3_2",
                        "v1_sec_2_1_1_1_p_5",
                        "v1_sec_4_2_tbl_2",
                    ]
                    v1_nodes = (
                        db.query(DocumentNodeModel)
                        .filter(
                            DocumentNodeModel.version_id == "ct200_manual_v1",
                            DocumentNodeModel.id.in_(target_node_ids)
                        )
                        .all()
                    )
                    if v1_nodes:
                        node_map = {n.id: n for n in v1_nodes}
                        ordered_nodes = [node_map[nid] for nid in target_node_ids if nid in node_map]
                        sel = Selection(
                            id="sel_ct200_baseline_suite",
                            name="CT-200 Core Baseline Requirements",
                            description="Comprehensive verification suite covering intended use, inflation, battery specifications, and error handling.",
                            document_id="ct200_manual",
                            version_id="ct200_manual_v1",
                            version_number="v1"
                        )
                        db.add(sel)
                        db.flush()
                        for idx, n in enumerate(ordered_nodes):
                            item = SelectionItem(
                                selection_id=sel.id,
                                node_id=n.id,
                                version_id=n.version_id,
                                logical_key=n.logical_key,
                                content_hash=n.content_hash,
                                order_index=idx
                            )
                            db.add(item)
                        db.commit()
                        logger.info(f"Default selection '{sel.id}' seeded successfully with {len(ordered_nodes)} nodes.")

                        try:
                            from app.llm.generator import QATestGeneratorService
                            from app.llm.store import JSONTestStore
                            store = JSONTestStore()
                            generator = QATestGeneratorService(store=store)
                            generator.generate_for_selection(
                                selection_id=sel.id,
                                db=db,
                                force_regenerate=False,
                                additional_instructions="Standard CT-200 baseline test suite verification"
                            )
                            logger.info("Default QA test cases pre-seeded successfully.")
                        except Exception as gen_err:
                            logger.warning(f"Could not pre-seed default QA test cases: {gen_err}")
    except Exception as e:
        logger.error(f"Database initialization error on startup: {e}")
    yield


app = FastAPI(
    title="Tri9T-CT200-Document-Intelligence API",
    version="1.0.0",
    description="Backend Document Intelligence, Version Management, and QA Test Generation Engine for CardioTrack CT-200 Technical Documentation.",
    docs_url=None,
    lifespan=lifespan
)

# Configure Allowed CORS Origins
default_origins = [
    "https://tri9t-ct-200-document-intelligence.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

env_origins = os.getenv("ALLOWED_ORIGINS", "")
if env_origins:
    custom_origins = [o.strip() for o in env_origins.split(",") if o.strip()]
    allowed_origins = list(set(default_origins + custom_origins))
else:
    allowed_origins = default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https:\/\/tri9t-ct-200-document-intelligence.*\.vercel\.app",
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


@app.get(
    "/api/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check endpoint alias under /api prefix"
)
def api_health_check(db: Session = Depends(get_db)):
    """Convenience alias for /health under the /api prefix."""
    return health_check(db)


# Include API Routers
app.include_router(api_router)


# ---------------------------------------------------------
# Custom Swagger UI Documentation & Stylesheet
# ---------------------------------------------------------
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Serves polished, enterprise Navy/Indigo themed Swagger UI matching the frontend."""
    response = get_swagger_ui_html(
        openapi_url=app.openapi_url or "/openapi.json",
        title=f"{app.title} - Swagger Documentation",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
        swagger_ui_parameters={
            "docExpansion": "list",
            "deepLinking": True,
            "filter": True,
            "displayRequestDuration": True,
            "persistAuthorization": True,
        }
    )
    custom_css = get_custom_swagger_css()
    html_content = response.body.decode("utf-8").replace(
        "</head>",
        f"<style>{custom_css}</style></head>"
    )
    return HTMLResponse(content=html_content)


@app.get("/static/swagger-custom.css", include_in_schema=False)
async def swagger_custom_css():
    """Dedicated endpoint serving custom Swagger UI CSS."""
    return Response(content=get_custom_swagger_css(), media_type="text/css")


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    """OAuth2 redirect helper for Swagger UI."""
    return get_swagger_ui_oauth2_redirect_html()


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)

