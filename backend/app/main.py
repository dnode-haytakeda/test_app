from fastapi import FastAPI, Request

from app.api.router import api_router
from app.core.version import APP_VERSION


app = FastAPI(
    title="my-app",
    service_version=APP_VERSION,
    description="フルスタック Web アプリケーション",
)

app.include_router(api_router)

