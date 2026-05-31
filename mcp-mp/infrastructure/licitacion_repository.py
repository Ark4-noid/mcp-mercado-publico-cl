from typing import Any, Optional
from domain.licitacion.entities import Licitacion
from domain.licitacion.repository import LicitacionRepository
from infrastructure.mercado_publico_client import (
    MercadoPublicoClient,
    fetch_json,
    validate_fecha,
    validate_estado_licitacion,
)

ENDPOINT = "licitaciones.json"


def _parse_listado(data: dict) -> list[Licitacion]:
    listado = data.get("Listado") or []
    return [Licitacion.model_validate(item) for item in listado]


class MercadoPublicoLicitacionRepository(LicitacionRepository):

    def __init__(self, client: Optional[MercadoPublicoClient] = None) -> None:
        self._client = client

    async def _fetch(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._client is not None:
            return await self._client.fetch_json(path, params)
        return await fetch_json(path, params)

    async def get_by_codigo(self, codigo: str) -> Optional[Licitacion]:
        data = await self._fetch(ENDPOINT, {"codigo": codigo})
        listado = _parse_listado(data)
        return listado[0] if listado else None

    async def list_hoy(self) -> list[Licitacion]:
        data = await self._fetch(ENDPOINT, {})
        return _parse_listado(data)

    async def list_activas(self) -> list[Licitacion]:
        data = await self._fetch(ENDPOINT, {"estado": "activas"})
        return _parse_listado(data)

    async def list_by_fecha(self, fecha: str) -> list[Licitacion]:
        validate_fecha(fecha)
        data = await self._fetch(ENDPOINT, {"fecha": fecha})
        return _parse_listado(data)

    async def list_by_estado(self, estado: str, fecha: Optional[str] = None) -> list[Licitacion]:
        estado_norm = validate_estado_licitacion(estado)
        params: dict = {"estado": estado_norm}
        if fecha:
            validate_fecha(fecha)
            params["fecha"] = fecha
        data = await self._fetch(ENDPOINT, params)
        return _parse_listado(data)

    async def list_by_organismo(self, codigo_organismo: str, fecha: Optional[str] = None) -> list[Licitacion]:
        params: dict = {"CodigoOrganismo": codigo_organismo}
        if fecha:
            validate_fecha(fecha)
            params["fecha"] = fecha
        data = await self._fetch(ENDPOINT, params)
        return _parse_listado(data)

    async def list_by_proveedor(self, codigo_proveedor: str, fecha: Optional[str] = None) -> list[Licitacion]:
        params: dict = {"CodigoProveedor": codigo_proveedor}
        if fecha:
            validate_fecha(fecha)
            params["fecha"] = fecha
        data = await self._fetch(ENDPOINT, params)
        return _parse_listado(data)
