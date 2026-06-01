import pytest
from unittest.mock import AsyncMock
from domain.licitacion.entities import Licitacion
from application.licitacion.use_cases import (
    ObtenerLicitacion,
    ListarLicitacionesHoy,
    ListarLicitacionesActivas,
    ListarLicitacionesPorFecha,
    ListarLicitacionesPorEstado,
    ListarLicitacionesPorOrganismo,
    ListarLicitacionesPorProveedor,
)


def _make_lic(**kwargs) -> Licitacion:
    return Licitacion.model_validate({"CodigoExterno": "1234", "Nombre": "Test", **kwargs})


@pytest.fixture
def repo():
    mock = AsyncMock()
    return mock


async def test_obtener_licitacion_ok(repo):
    repo.get_by_codigo.return_value = _make_lic()
    result = await ObtenerLicitacion(repo).execute("1234")
    assert result.CodigoExterno == "1234"


async def test_obtener_licitacion_no_encontrada(repo):
    repo.get_by_codigo.return_value = None
    with pytest.raises(ValueError, match="No se encontró"):
        await ObtenerLicitacion(repo).execute("XXXX")


async def test_listar_hoy(repo):
    repo.list_hoy.return_value = [_make_lic(), _make_lic()]
    result = await ListarLicitacionesHoy(repo).execute()
    assert len(result) == 2


async def test_listar_activas(repo):
    repo.list_activas.return_value = [_make_lic()]
    result = await ListarLicitacionesActivas(repo).execute()
    assert len(result) == 1


async def test_listar_por_fecha_valida(repo):
    repo.list_by_fecha.return_value = [_make_lic()]
    result = await ListarLicitacionesPorFecha(repo).execute("01012024")
    repo.list_by_fecha.assert_called_once_with("01012024")
    assert len(result) == 1


async def test_listar_por_fecha_invalida(repo):
    with pytest.raises(ValueError, match="ddmmaaaa"):
        await ListarLicitacionesPorFecha(repo).execute("2024-01-01")


async def test_listar_por_estado(repo):
    repo.list_by_estado.return_value = [_make_lic()]
    result = await ListarLicitacionesPorEstado(repo).execute("adjudicada")
    assert len(result) == 1


async def test_listar_por_organismo(repo):
    repo.list_by_organismo.return_value = []
    result = await ListarLicitacionesPorOrganismo(repo).execute("6945")
    repo.list_by_organismo.assert_called_once_with("6945", None)


async def test_listar_por_proveedor(repo):
    repo.list_by_proveedor.return_value = []
    result = await ListarLicitacionesPorProveedor(repo).execute("17793", "01012024")
    repo.list_by_proveedor.assert_called_once_with("17793", "01012024")
