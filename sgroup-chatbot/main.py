import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.router import router
from config.settings import settings

app = FastAPI(
    title="SGroup AI Assistant",
    version="1.0.0",
    description="Multi-agent chatbot powered by Gemini + LangGraph",
)

app.include_router(router, prefix="/api")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def serve_ui() -> FileResponse:
    return FileResponse("static/index.html")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
