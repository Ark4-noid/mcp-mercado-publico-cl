"""Factories for tenant-scoped repositories.

Each factory takes a `TenantContext` and returns a repository wired to that
tenant's ChileCompra ticket. The ticket is resolved from the tenant's profile;
no environment fallback to avoid cross-tenant leakage.
"""
from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from core.settings import Settings
from core.tenant_context import TenantContext

if TYPE_CHECKING:
    from browser_pool.pool import BrowserPool


logger = logging.getLogger("mp.repos.factory")


async def _resolve_ticket(ctx: TenantContext) -> str:
    """Resolve the ChileCompra ticket from the tenant profile.

    Resolution order:
      1. profile['ticket'] (canonical, multi-tenant)
      2. raise ValueError if missing or empty - the caller (middleware) can
         turn this into an HTTP 400.
    """
    profile = await ctx.profile_store.get()
    if profile is not None:
        ticket = profile.get("ticket")
        if isinstance(ticket, str) and ticket:
            return ticket
    raise ValueError(
        f"Tenant {ctx.tenant_id!r} has no ChileCompra ticket configured. "
        "Set profile['ticket'] via guardar_perfil_proveedor."
    )


async def make_licitacion_repo(
    ctx: TenantContext,
    http: httpx.AsyncClient,
    settings: Settings,
) -> Any:
    """Build a `MercadoPublicoLicitacionRepository` scoped to one tenant."""
    from infrastructure.licitacion_repository import (
        MercadoPublicoLicitacionRepository,
    )
    from infrastructure.mercado_publico_client import MercadoPublicoClient

    ticket = await _resolve_ticket(ctx)
    client = MercadoPublicoClient(
        base_url=str(settings.chilecompra_base_url),
        ticket=ticket,
        http=http,
    )
    return MercadoPublicoLicitacionRepository(client)


async def make_oc_repo(
    ctx: TenantContext,
    http: httpx.AsyncClient,
    settings: Settings,
) -> Any:
    """Build a `MercadoPublicoOrdenCompraRepository` scoped to one tenant."""
    from infrastructure.mercado_publico_client import MercadoPublicoClient
    from infrastructure.orden_compra_repository import (
        MercadoPublicoOrdenCompraRepository,
    )

    ticket = await _resolve_ticket(ctx)
    client = MercadoPublicoClient(
        base_url=str(settings.chilecompra_base_url),
        ticket=ticket,
        http=http,
    )
    return MercadoPublicoOrdenCompraRepository(client)


_COOKIES_SECRET_NAME = "cookies"


class ScraperRepo:
    """Tenant-scoped scraper.

    Cookies live in ``ctx.secrets`` under the ``cookies`` key as a JSON-
    encoded list (Playwright cookie dict format). Each operation:

      1. Loads cookies from ``ctx.secrets``.
      2. Reuses the shared MPBrowser (which respects an injected cookies_path)
         via a temp dir + the legacy ``auth.save_cookies`` flow — the MPBrowser
         API is acoplado a filesystem paths, así que materializamos las cookies
         en un temp file por request (igual que hicimos con los generators
         en Chunk 2). Esta es la opción (b) discutida en el plan: mantiene
         MPBrowser intacto y aísla el concern multi-tenant en este wrapper.
      3. Downloads documentos a un temp dir y los sube a ``ctx.storage`` bajo
         ``ofertas/<codigo>/documentos/<nombre>``.

    Note on BrowserPool: el MPBrowser legacy abre su propio Playwright y su
    propio Chromium, por lo que NO usamos ``pool.acquire_context`` todavía.
    El pool sigue existiendo como infraestructura compartida para futuros
    refactors (Sprint 2) donde MPBrowser sea descompuesto.
    """

    def __init__(self, ctx: TenantContext, pool: "BrowserPool | None") -> None:
        self._ctx = ctx
        self._pool = pool  # reservado para Sprint 2

    async def _load_cookies(self) -> list[dict[str, Any]]:
        raw = await self._ctx.secrets.get_secret(_COOKIES_SECRET_NAME)
        if not raw:
            return []
        try:
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, list):
                return data
            return []
        except (UnicodeDecodeError, json.JSONDecodeError):
            return []

    async def verificar_sesion(self) -> dict[str, Any]:
        cookies = await self._load_cookies()
        return {
            "tenant_id": self._ctx.tenant_id,
            "tiene_cookies": bool(cookies),
            "cantidad_cookies": len(cookies),
            "mensaje": (
                "Sesión disponible para este tenant."
                if cookies
                else "Sin cookies. Subí tus cookies con `subir_cookies_scraper`."
            ),
        }

    async def descargar_documentacion(self, codigo: str) -> dict[str, Any]:
        try:
            from scraper.browser import MPBrowser  # type: ignore[import-untyped]
            from scraper.parser import DocumentParser  # type: ignore[import-untyped]
        except ImportError as exc:
            return {
                "ok": False,
                "error": f"Scraper no disponible: {exc}",
            }

        cookies = await self._load_cookies()
        if not cookies:
            return {
                "ok": False,
                "error": (
                    "No hay cookies de sesión para este tenant. "
                    "Subí tus cookies con `subir_cookies_scraper` (BYO cookies)."
                ),
                "codigo": codigo,
            }

        with tempfile.TemporaryDirectory(prefix="mp-scraper-") as tmpdir:
            tmp = Path(tmpdir)
            cookies_path = tmp / "cookies.json"
            cookies_path.write_text(
                json.dumps(cookies), encoding="utf-8"
            )
            doc_dir = tmp / "documentos"
            doc_dir.mkdir(parents=True, exist_ok=True)

            try:
                async with MPBrowser(
                    headless=True, cookies_path=cookies_path
                ) as browser:
                    ficha_url = await browser.buscar_licitacion(codigo)
                    if not ficha_url:
                        return {
                            "ok": False,
                            "error": (
                                f"No se pudo encontrar la licitación {codigo}."
                            ),
                            "codigo": codigo,
                        }

                    documentos = await browser.extraer_links_documentos()
                    if not documentos:
                        return {
                            "ok": True,
                            "codigo": codigo,
                            "ficha_url": ficha_url,
                            "documentos_descargados": [],
                            "advertencia": (
                                "No se encontraron documentos anexos en la ficha."
                            ),
                        }

                    descargados = await browser.descargar_documentos_con_sesion(
                        documentos, doc_dir
                    )
            except Exception as exc:  # noqa: BLE001
                logger.exception("scraper error for tenant=%s", self._ctx.tenant_id)
                return {
                    "ok": False,
                    "error": f"Error en scraper: {exc}",
                    "tipo_error": type(exc).__name__,
                    "codigo": codigo,
                }

            # Upload each downloaded document to tenant storage.
            uploaded: list[str] = []
            for local_path in descargados:
                key = f"ofertas/{codigo}/documentos/{local_path.name}"
                data = local_path.read_bytes()
                await self._ctx.storage.write_bytes(key, data)
                uploaded.append(key)

            # Best-effort resumen.txt next to documentos/.
            try:
                texto = DocumentParser.parse_directory(doc_dir)
                resumen_key = f"ofertas/{codigo}/resumen_licitacion.md"
                await self._ctx.storage.write_text(resumen_key, texto)
            except Exception as exc:  # noqa: BLE001
                logger.warning("resumen parsing failed: %s", exc)
                resumen_key = None

            return {
                "ok": True,
                "codigo": codigo,
                "tenant_id": self._ctx.tenant_id,
                "ficha_url": ficha_url,
                "total_documentos_encontrados": len(documentos),
                "documentos_descargados": uploaded,
                "resumen_key": resumen_key,
            }


def make_scraper_repo(
    ctx: TenantContext,
    pool: "BrowserPool | None" = None,
) -> ScraperRepo:
    """Build a tenant-scoped scraper repository.

    Cookies are loaded from ``ctx.secrets`` on every call; documents are
    written through ``ctx.storage`` under the ``ofertas/<codigo>/`` prefix.
    """
    return ScraperRepo(ctx, pool)
