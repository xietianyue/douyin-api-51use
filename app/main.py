"""Private Douyin parsing service used by the 51use toolbox backend."""

from fastapi import FastAPI

from app.api.router import router as api_router

app = FastAPI(
    title="51use Douyin Parser",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(api_router)
