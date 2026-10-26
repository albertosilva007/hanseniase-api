from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import Base, SessionLocal, engine
from .missoes import ajusta_pct_minimo, gera_missoes
from .routers import admin, jogo, publico
from .seed import carrega_questoes, garante_admin

STATIC = Path(__file__).parent / "static"
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        garante_admin(db)
        if settings.seed_on_startup:
            carrega_questoes(db)
            gera_missoes(db)  # só gera se ainda não houver trilhas
        ajusta_pct_minimo(db)
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_methods=["*"],
                   allow_headers=["*"], allow_credentials=False)
app.include_router(publico.router)
app.include_router(admin.router)
app.include_router(jogo.router)


@app.get("/api/health", tags=["infra"])
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def pagina_quiz():
    return FileResponse(STATIC / "index.html")


@app.get("/admin", include_in_schema=False)
def pagina_admin():
    return FileResponse(STATIC / "admin.html")


@app.get("/jogo", include_in_schema=False)
def pagina_jogo():
    return FileResponse(STATIC / "jogo.html")


@app.get("/admin/banco", include_in_schema=False)
def pagina_banco():
    return FileResponse(STATIC / "banco.html")


@app.get("/dashboard", include_in_schema=False)
def pagina_dashboard():
    return FileResponse(STATIC / "dashboard.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
