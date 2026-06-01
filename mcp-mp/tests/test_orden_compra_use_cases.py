import pytest
from unittest.mock import AsyncMock
from domain.orden_compra.entities import OrdenCompra
from application.orden_compra.use_cases import (
    ObtenerOrdenCompra,
    ListarOrdenesHoy,
    ListarOrdenesPorFecha,
    ListarOrdenesPorEstado,
    ListarOrdenesPorOrganismo,
    ListarOrdenesPorProveedor,
)


def _make_oc(**kwargs) -> OrdenCompra:
    return OrdenCompra.model_validate({"Codigo": "111-1-SE14", "Nombre": "OC Test", **kwargs})


@pytest.fixture
def repo():
    return AsyncMock()


async def test_obtener_oc_ok(repo):
    repo.get_by_codigo.return_value = _make_oc()
    result = await ObtenerOrdenCompra(repo).execute("111-1-SE14")
    assert result.Codigo == "111-1-SE14"


async def test_obtener_oc_no_encontrada(repo):
    repo.get_by_codigo.return_value = None
    with pytest.raises(ValueError, match="No se encontró"):
        await ObtenerOrdenCompra(repo).execute("XXXX")


async def test_listar_hoy(repo):
    repo.list_hoy.return_value = [_make_oc(), _make_oc()]
    result = await ListarOrdenesHoy(repo).execute()
    assert len(result) == 2


async def test_listar_por_fecha_valida(repo):
    repo.list_by_fecha.return_value = [_make_oc()]
    result = await ListarOrdenesPorFecha(repo).execute("01012024")
    repo.list_by_fecha.assert_called_once_with("01012024")


async def test_listar_por_fecha_invalida(repo):
    with pytest.raises(ValueError, match="ddmmaaaa"):
        await ListarOrdenesPorFecha(repo).execute("2024-01-01")


async def test_listar_por_estado(repo):
    repo.list_by_estado.return_value = [_make_oc()]
    result = await ListarOrdenesPorEstado(repo).execute("aceptada")
    assert len(result) == 1


async def test_listar_por_organismo(repo):
    repo.list_by_organismo.return_value = []
    await ListarOrdenesPorOrganismo(repo).execute("6945")
    repo.list_by_organismo.assert_called_once_with("6945", None)


async def test_listar_por_proveedor(repo):
    repo.list_by_proveedor.return_value = []
    await ListarOrdenesPorProveedor(repo).execute("17793", "01012024")
    repo.list_by_proveedor.assert_called_once_with("17793", "01012024")
