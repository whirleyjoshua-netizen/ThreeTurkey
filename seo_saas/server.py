from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from seo_saas.storage.database import connect, close
from seo_saas.routes.waitlist import router as waitlist_router
from seo_saas.routes.admin import router as admin_router
from seo_saas.routes.checkout import router as checkout_router
from seo_saas.routes.auth import router as auth_router
from seo_saas.routes.dashboard import router as dashboard_router

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect()
    yield
    await close()


app = FastAPI(title="Three Turkey", lifespan=lifespan)
app.include_router(waitlist_router)
app.include_router(admin_router)
app.include_router(checkout_router)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def landing():
    return FileResponse(STATIC / "index.html", media_type="text/html")


@app.get("/dashboard")
async def dashboard():
    return FileResponse(STATIC / "dashboard.html", media_type="text/html")


@app.get("/robots.txt")
async def robots():
    return FileResponse(STATIC / "robots.txt", media_type="text/plain")


@app.get("/sitemap.xml")
async def sitemap():
    return FileResponse(STATIC / "sitemap.xml", media_type="application/xml")
