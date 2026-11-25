import asyncio
import uvicorn

from app.config import settings
from app.main import app


async def serve_all() -> None:
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
