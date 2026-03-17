from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from seo_saas.storage.database import connect, close
from seo_saas.routes.waitlist import router as waitlist_router

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect()
    yield
    await close()


app = FastAPI(title="Marqet", lifespan=lifespan)
app.include_router(waitlist_router)
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def landing():
    return FileResponse(STATIC / "index.html", media_type="text/html")
