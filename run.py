import asyncio
import socket
import uvicorn

from app.config import settings
from app.main import app


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


async def serve_all() -> None:
    lan_ip = _local_ip()
    print("=" * 60)
    print("UstaBor ishga tushdi!")
    print(f"  Shu kompyuterdan:")
    print(f"    Mijoz sayti:  http://127.0.0.1:{settings.PORT}/")
    print(f"    Mijoz paneli: http://127.0.0.1:{settings.CLIENT_PORT}/")
    print(f"    Admin paneli: http://127.0.0.1:{settings.ADMIN_PORT}/")
    print(f"  Boshqa kompyuter va telefonlardan (bir Wi-Fi da):")
    print(f"    Mijoz sayti:  http://{lan_ip}:{settings.PORT}/")
    print(f"    Mijoz paneli: http://{lan_ip}:{settings.CLIENT_PORT}/")
    print(f"    Admin paneli: http://{lan_ip}:{settings.ADMIN_PORT}/")
    print("=" * 60)

    ports = [settings.PORT, settings.CLIENT_PORT, settings.ADMIN_PORT]
    servers = [
        uvicorn.Server(
            uvicorn.Config(
                app,
                host=settings.HOST,
                port=port,
                log_level="info",
            )
        )
        for port in ports
    ]
    await asyncio.gather(*(srv.serve() for srv in servers))


if __name__ == "__main__":
    asyncio.run(serve_all())
