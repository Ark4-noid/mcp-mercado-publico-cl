"""MCP tools for the document scraper - tenant-scoped.

All scraper tools now go through `ScraperRepo` (built per call from
`current_tenant()`), so cookies and downloaded documents are isolated per
tenant via `ctx.secrets` and `ctx.storage`. The legacy global
`~/.mp-mcp/cookies.json` is no longer used.

For multi-tenant deployments the user must upload cookies once per tenant
via `subir_cookies_scraper`. For the local stdio path, the legacy migration
(see `migrations.legacy`) seeds the `local` tenant's secrets store from the
old cookies file when present.
"""
from __future__ import annotations

import json
from typing import Any

from core.tenant_context import current_tenant
from interfaces.mcp.runtime import RuntimeNotReadyError, get_browser_pool
from interfaces.mcp.server import mcp
from repos.factory import make_scraper_repo


def _safe_get_pool() -> Any:
    """Return the BrowserPool if available, else None.

    The pool is optional for cookies-only operations (verificar_sesion,
    subir_cookies). It is required for actual scraping.
    """
    try:
        return get_browser_pool()
    except RuntimeNotReadyError:
        return None


@mcp.tool()
async def verificar_sesion_scraper() -> dict[str, Any]:
    """Verifica si hay cookies de sesión guardadas para el scraper en este tenant.

    En modo multi-tenant las cookies viven en SecretsProvider por tenant.
    Esta tool no autentica contra el portal — solo reporta si hay cookies
    disponibles. Si no las hay, usá `subir_cookies_scraper`.
    """
    try:
        ctx = current_tenant()
        scraper = make_scraper_repo(ctx, _safe_get_pool())
        return await scraper.verificar_sesion()
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


@mcp.tool()
async def subir_cookies_scraper(cookies_json: str) -> dict[str, Any]:
    """Sube cookies de sesión del portal de Mercado Público para este tenant.

    En multi-tenant cada usuario debe hacer login en su máquina (por ejemplo
    con `mp-scraper login` localmente), exportar las cookies del navegador y
    subir el JSON resultante con esta tool. Las cookies se guardan cifradas
    por tenant en SecretsProvider.

    Args:
        cookies_json: String JSON con una lista de cookies en formato
            Playwright (name, value, domain, path, etc.).
    """
    try:
        ctx = current_tenant()
        try:
            cookies = json.loads(cookies_json)
        except json.JSONDecodeError as exc:
            return {"error": f"cookies_json no es JSON válido: {exc}"}
        if not isinstance(cookies, list):
            return {
                "error": "cookies_json debe ser una lista JSON de cookies.",
            }
        await ctx.secrets.set_secret(
            "cookies", cookies_json.encode("utf-8")
        )
        return {
            "ok": True,
            "tenant_id": ctx.tenant_id,
            "cantidad": len(cookies),
        }
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


@mcp.tool()
async def descargar_documentacion_licitacion(codigo: str) -> dict[str, Any]:
    """Descarga todos los documentos anexos de una licitación.

    Los documentos se guardan en el storage del tenant bajo
    `ofertas/<codigo>/documentos/`, y un resumen markdown bajo
    `ofertas/<codigo>/resumen_licitacion.md`.

    Requiere que el tenant tenga cookies cargadas previamente con
    `subir_cookies_scraper`.

    Args:
        codigo: Código de la licitación (ej: '1005498-5-LE26').
    """
    try:
        ctx = current_tenant()
        pool = _safe_get_pool()
        scraper = make_scraper_repo(ctx, pool)
        return await scraper.descargar_documentacion(codigo)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e), "codigo": codigo}


@mcp.tool()
async def obtener_info_licitacion_con_documentos(
    codigo: str,
) -> dict[str, Any]:
    """Obtiene info combinada de una licitación (API + documentos del scraper).

    Combina los datos estructurados de la API con la descarga de documentos
    desde el portal web. Ambas partes son tenant-scoped: la API usa el
    ticket del perfil del tenant; el scraper usa las cookies del tenant.

    Args:
        codigo: Código de la licitación (ej: '1005498-5-LE26').
    """
    try:
        from application.licitacion.use_cases import ObtenerLicitacion
        from interfaces.mcp.runtime import get_http, get_runtime_settings
        from repos.factory import make_licitacion_repo

        ctx = current_tenant()
        out: dict[str, Any] = {"codigo": codigo, "tenant_id": ctx.tenant_id}

        # API side.
        try:
            repo = await make_licitacion_repo(
                ctx, get_http(), get_runtime_settings()
            )
            lic = await ObtenerLicitacion(repo).execute(codigo)
            out["info_api"] = lic.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            out["error_api"] = str(exc)

        # Scraper side.
        scraper = make_scraper_repo(ctx, _safe_get_pool())
        scraper_result = await scraper.descargar_documentacion(codigo)
        out["scraper"] = scraper_result
        out["documentos_disponibles"] = bool(
            scraper_result.get("ok")
            and scraper_result.get("documentos_descargados")
        )
        return out
    except Exception as e:  # noqa: BLE001
        return {"error": str(e), "codigo": codigo}
