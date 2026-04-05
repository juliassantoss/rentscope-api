from fastapi import FastAPI
from app.routers import paises, cidades, filtros, auth, history, renda, municipios
from app.routers.ai import router as ai_router

app = FastAPI(title="RentScope API")

app.include_router(paises.router)
app.include_router(cidades.router)
app.include_router(filtros.router)
app.include_router(auth.router)
app.include_router(history.router)
app.include_router(renda.router)
app.include_router(municipios.router)
app.include_router(ai_router)

@app.get("/health")
def health():
    return {"status": "ok"}