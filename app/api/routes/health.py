from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/health")
async def health_check():
    return JSONResponse(
        content={
            "status": "healthy",
            "service": "cerebras-anthropic-gateway",
            "version": "1.0.0"
        }
    )


@router.get("/")
async def root():
    return JSONResponse(
        content={
            "name": "Cerebras Anthropic Gateway",
            "version": "1.0.0",
            "description": "Drop-in Anthropic API replacement backed by Cerebras"
        }
    )
