from fastapi import FastAPI
from app.routers import paises, cidades, filtros

app = FastAPI(title="RentScope API")


app.include_router(paises.router)
app.include_router(cidades.router)
app.include_router(filtros.router)


@app.get("/health")
def health():
    return {"status": "ok"}
