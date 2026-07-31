from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def system_health(request: Request):
    return {
        "status": "ok",
        "server_ip": request.url.hostname or "localhost",
    }
