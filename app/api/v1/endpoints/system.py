import socket

from fastapi import APIRouter, Request

router = APIRouter()


def _get_server_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


@router.get("/health")
async def system_health(request: Request):
    return {
        "status": "ok",
        "server_ip": _get_server_ip(),
    }