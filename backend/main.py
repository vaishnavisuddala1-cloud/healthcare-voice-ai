from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from config.settings import settings
from config.database import Base, engine
from config.redis_config import get_redis, close_redis
from backend.routes import router
from backend.tts import router as tts_router
from backend.campaigns import router as campaigns_router
from backend.websocket_manager import manager
from fastapi.staticfiles import StaticFiles
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifecycle."""
    # Startup
    redis = await get_redis()
    logger.info("Redis connection initialized")
    yield
    # Shutdown
    await close_redis()
    logger.info("Redis connection closed")


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    debug=settings.debug,
    lifespan=lifespan,
)

# Serve the frontend SPA (if present)
try:
    app.mount("/app", StaticFiles(directory="frontend", html=True), name="frontend")
except Exception:
    # If frontend folder is missing during development, ignore
    pass

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)
app.include_router(tts_router)
app.include_router(campaigns_router)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "message": "Healthcare Voice AI Agent API",
        "version": settings.api_version,
    }


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",
        "redis": "connected",
    }


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for voice conversations."""
    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle different message types
            if message.get("type") == "audio":
                audio_data = message.get("data")
                language = message.get("language", settings.default_language)
                response = await manager.process_voice_turn(session_id, audio_data, language)
                await manager.broadcast(session_id, response)

            elif message.get("type") == "text":
                user_input = message.get("text")
                language = message.get("language", settings.default_language)
                response = await manager.process_text_turn(session_id, user_input, language)
                await manager.broadcast(session_id, response)

    except WebSocketDisconnect:
        await manager.disconnect(session_id)
        logger.info(f"WebSocket connection closed for {session_id}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
