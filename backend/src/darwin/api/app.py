from fastapi import FastAPI

app = FastAPI(title="darwin-chess")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
