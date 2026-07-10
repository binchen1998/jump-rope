import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import MEDIA_DIR
from .db import close_db
from .routers import admin, competitions, featured, videos

BASE_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = BASE_DIR.parent / "frontend" / "dist"

NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_db()


app = FastAPI(title="Jump Rope 跳绳", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)
app.include_router(videos.router)
app.include_router(featured.router)
app.include_router(competitions.router)


@app.get("/api/health")
async def health():
    return {"ok": True, "app": "jump-rope"}


if MEDIA_DIR.exists():
    app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


_assets = DIST_DIR / "assets"
if _assets.exists():
    app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")


def _serve_index():
    index = DIST_DIR / "index.html"
    if not index.exists():
        return HTMLResponse(
            "<h1>前端尚未构建</h1><p>开发模式请运行 <code>cd frontend && npm run dev</code>，"
            "或构建后 <code>npm run build</code>。</p>",
            status_code=200,
        )
    return FileResponse(str(index), headers=NO_CACHE)


@app.get("/")
async def index():
    return _serve_index()


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path.startswith("assets/") or full_path.startswith("media/"):
        raise HTTPException(status_code=404)
    candidate = DIST_DIR / full_path
    if candidate.is_file():
        return FileResponse(str(candidate))
    return _serve_index()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
