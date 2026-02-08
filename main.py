from fastapi import FastAPI

app = FastAPI(title="RentScope API")


@app.get("/health")
def health():
    return {"status": "ok"}
