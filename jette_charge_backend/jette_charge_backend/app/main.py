from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import init_db
from app.routers import admin, charging_stats, dev, stations

settings = get_settings()

app = FastAPI(title="JETTE CHARGE 김종규 담당 백엔드", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()


@app.get(f"{settings.api_prefix}/health", tags=["health"])
async def health():
    return {"success": True, "message": "서버 정상 동작", "data": {"app": settings.app_name, "env": settings.app_env}}


app.include_router(stations.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(dev.router, prefix=settings.api_prefix)
app.include_router(charging_stats.router, prefix=settings.api_prefix)
