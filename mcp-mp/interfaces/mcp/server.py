from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

from infrastructure.mercado_publico_client import get_ticket

mcp = FastMCP(
    "mercado-publico",
    instructions="Servidor MCP para consultar licitaciones y órdenes de compra de la API de Mercado Público de ChileCompra.",
)


def create_app() -> FastAPI:
    # Valida el ticket al arrancar (lanza RuntimeError si no está configurado)
    get_ticket()

    from interfaces.mcp import tools  # noqa: F401 — registra los tools en mcp

    # streamable_http_app() expone el endpoint MCP en /mcp y maneja su propio
    # session manager via lifespan. Hay que propagarlo al FastAPI host o las
    # sesiones nunca se inicializan.
    mcp_app = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        async with mcp_app.router.lifespan_context(mcp_app):
            yield

    app = FastAPI(title="MCP Mercado Público", lifespan=lifespan)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # El MCP app ya define /mcp internamente. Montamos en / para que el
    # endpoint público final sea /mcp.
    app.mount("/", mcp_app)

    return app
