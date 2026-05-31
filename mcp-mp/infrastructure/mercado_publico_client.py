import os
import re
import httpx
from typing import Any, Optional

BASE_URL = os.getenv(
    "MERCADO_PUBLICO_BASE_URL",
    "https://api.mercadopublico.cl/servicios/v1/publico",
)


class MercadoPublicoClient:
    """Multi-tenant HTTP client to the ChileCompra public API.

    Each instance is bound to a single ticket (resolved from a tenant profile)
    and a shared `httpx.AsyncClient`. The legacy `fetch_json` function below
    is preserved for backwards compatibility with code that still reads
    ``MERCADO_PUBLICO_TICKET`` from the environment.
    """

    def __init__(
        self,
        base_url: str,
        ticket: str,
        http: httpx.AsyncClient,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._ticket = ticket
        self._http = http

    async def fetch_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        merged = {**params, "ticket": self._ticket}
        url = f"{self._base_url}/{path}"
        try:
            response = await self._http.get(url, params=merged)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"Timeout al conectar con la API de Mercado Público ({url})."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Error HTTP {exc.response.status_code} desde la API de Mercado Público: "
                f"{exc.response.text[:200]}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Error de conexión con la API de Mercado Público: {exc}"
            ) from exc


def get_ticket() -> str:
    ticket = os.getenv("MERCADO_PUBLICO_TICKET", "")
    if not ticket:
        raise RuntimeError(
            "La variable de entorno MERCADO_PUBLICO_TICKET no está configurada. "
            "Obtén tu ticket en https://www.mercadopublico.cl y defínela antes de iniciar el servidor."
        )
    return ticket


def validate_fecha(fecha: str) -> str:
    """Valida que la fecha esté en formato ddmmaaaa."""
    if not re.fullmatch(r"\d{8}", fecha):
        raise ValueError(
            f"Formato de fecha inválido: '{fecha}'. Se esperaba formato ddmmaaaa (e.g., '02022014')."
        )
    return fecha


ESTADOS_LICITACION = {"publicada", "cerrada", "desierta", "adjudicada", "revocada", "suspendida", "todos"}
ESTADOS_OC = {
    "enviadaproveedor", "aceptada", "cancelada", "recepcionconforme",
    "pendienterecepcion", "recepcionaceptadacialmente", "recepecionconformeincompleta", "todos",
}


def validate_estado_licitacion(estado: str) -> str:
    normalized = estado.lower()
    if normalized not in ESTADOS_LICITACION:
        raise ValueError(
            f"Estado inválido: '{estado}'. Estados válidos: {', '.join(sorted(ESTADOS_LICITACION))}."
        )
    return normalized


def validate_estado_oc(estado: str) -> str:
    normalized = estado.lower()
    if normalized not in ESTADOS_OC:
        raise ValueError(
            f"Estado inválido: '{estado}'. Estados válidos: {', '.join(sorted(ESTADOS_OC))}."
        )
    return normalized


async def fetch_json(path: str, params: dict[str, Any]) -> dict:
    params["ticket"] = get_ticket()
    url = f"{BASE_URL}/{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            raise RuntimeError(f"Timeout al conectar con la API de Mercado Público ({url}).")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Error HTTP {e.response.status_code} desde la API de Mercado Público: {e.response.text[:200]}"
            )
        except httpx.RequestError as e:
            raise RuntimeError(f"Error de conexión con la API de Mercado Público: {e}")
