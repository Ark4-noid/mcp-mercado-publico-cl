"""MCP tools wired to the per-request TenantContext.

All repos are built per-call via factories (`make_licitacion_repo`,
`make_oc_repo`) using the current tenant's profile_store + the shared
runtime (`get_http()`, `get_runtime_settings()`). No module-level
singletons - tenant isolation is enforced by ContextVar.

File outputs go through `ctx.storage.write_bytes(...)`; the generators
still write to a local Path, so we use a `tempfile.TemporaryDirectory`
to materialize them and then upload the bytes to the tenant's storage.
This keeps the generator API untouched (backwards-compat) and isolates
the multi-tenant concern to this layer.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Optional

from core.tenant_context import current_tenant
from interfaces.mcp.runtime import get_http, get_runtime_settings
from interfaces.mcp.server import mcp
from repos.factory import make_licitacion_repo, make_oc_repo, make_scraper_repo

from application.licitacion.use_cases import (
    BuscarLicitacionesPorNombre,
    BuscarLicitacionesSoftware,
    ListarLicitacionesActivas,
    ListarLicitacionesHoy,
    ListarLicitacionesPorEstado,
    ListarLicitacionesPorFecha,
    ListarLicitacionesPorOrganismo,
    ListarLicitacionesPorProveedor,
    ObtenerLicitacion,
)
from application.orden_compra.use_cases import (
    ListarOrdenesHoy,
    ListarOrdenesPorEstado,
    ListarOrdenesPorFecha,
    ListarOrdenesPorOrganismo,
    ListarOrdenesPorProveedor,
    ObtenerOrdenCompra,
)


# ─── Licitaciones ────────────────────────────────────────────────────────────


@mcp.tool()
async def obtener_licitacion(codigo: str) -> dict[str, Any]:
    """Obtiene el detalle completo de una licitación de Mercado Público por su código.
    Ejemplo de código: '1509-5-L114'. Retorna todos los campos incluyendo comprador,
    fechas, ítems y adjudicación."""
    try:
        ctx = current_tenant()
        repo = await make_licitacion_repo(ctx, get_http(), get_runtime_settings())
        lic = await ObtenerLicitacion(repo).execute(codigo)
        return lic.model_dump(mode="json")
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def listar_licitaciones_hoy() -> dict[str, Any]:
    """Lista todas las licitaciones publicadas en el día actual en todos sus estados."""
    try:
        ctx = current_tenant()
        repo = await make_licitacion_repo(ctx, get_http(), get_runtime_settings())
        lics = await ListarLicitacionesHoy(repo).execute()
        return {
            "cantidad": len(lics),
            "licitaciones": [l.model_dump(mode="json") for l in lics],
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def listar_licitaciones_activas() -> dict[str, Any]:
    """Lista únicamente las licitaciones activas/publicadas al día de hoy en Mercado Público."""
    try:
        ctx = current_tenant()
        repo = await make_licitacion_repo(ctx, get_http(), get_runtime_settings())
        lics = await ListarLicitacionesActivas(repo).execute()
        return {
            "cantidad": len(lics),
            "licitaciones": [l.model_dump(mode="json") for l in lics],
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def listar_licitaciones_por_fecha(fecha: str) -> dict[str, Any]:
    """Lista todas las licitaciones de una fecha específica.
    El parámetro 'fecha' debe estar en formato ddmmaaaa (ejemplo: '02022014' para el 2 de febrero de 2014)."""
    try:
        ctx = current_tenant()
        repo = await make_licitacion_repo(ctx, get_http(), get_runtime_settings())
        lics = await ListarLicitacionesPorFecha(repo).execute(fecha)
        return {
            "cantidad": len(lics),
            "licitaciones": [l.model_dump(mode="json") for l in lics],
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def listar_licitaciones_por_estado(
    estado: str, fecha: Optional[str] = None
) -> dict[str, Any]:
    """Lista licitaciones filtradas por estado. Si no se especifica fecha, usa el día actual.
    Estados válidos: Publicada, Cerrada, Desierta, Adjudicada, Revocada, Suspendida, Todos.
    Fecha en formato ddmmaaaa (opcional)."""
    try:
        ctx = current_tenant()
        repo = await make_licitacion_repo(ctx, get_http(), get_runtime_settings())
        lics = await ListarLicitacionesPorEstado(repo).execute(estado, fecha)
        return {
            "cantidad": len(lics),
            "licitaciones": [l.model_dump(mode="json") for l in lics],
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def listar_licitaciones_por_organismo(
    codigo_organismo: str, fecha: Optional[str] = None
) -> dict[str, Any]:
    """Lista las licitaciones publicadas por un organismo público específico.
    El 'codigo_organismo' es el código numérico del organismo (ejemplo: '6945').
    Fecha en formato ddmmaaaa (opcional, por defecto día actual)."""
    try:
        ctx = current_tenant()
        repo = await make_licitacion_repo(ctx, get_http(), get_runtime_settings())
        lics = await ListarLicitacionesPorOrganismo(repo).execute(
            codigo_organismo, fecha
        )
        return {
            "cantidad": len(lics),
            "licitaciones": [l.model_dump(mode="json") for l in lics],
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def listar_licitaciones_por_proveedor(
    codigo_proveedor: str, fecha: Optional[str] = None
) -> dict[str, Any]:
    """Lista las licitaciones asociadas a un proveedor específico.
    El 'codigo_proveedor' es el código numérico del proveedor (ejemplo: '17793').
    Fecha en formato ddmmaaaa (opcional, por defecto día actual)."""
    try:
        ctx = current_tenant()
        repo = await make_licitacion_repo(ctx, get_http(), get_runtime_settings())
        lics = await ListarLicitacionesPorProveedor(repo).execute(
            codigo_proveedor, fecha
        )
        return {
            "cantidad": len(lics),
            "licitaciones": [l.model_dump(mode="json") for l in lics],
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def buscar_licitaciones_por_nombre(
    query: str,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
) -> dict[str, Any]:
    """Busca licitaciones cuyo nombre o descripción contengan el texto indicado.
    Si no se especifican fechas, busca entre las licitaciones activas del día.
    Si se especifican, consulta la API día a día en el rango y filtra en memoria.
    Fechas en formato ddmmaaaa. Rango máximo: 30 días.
    Ejemplo: query='equipos computacionales', fecha_inicio='01032024', fecha_fin='07032024'."""
    try:
        ctx = current_tenant()
        repo = await make_licitacion_repo(ctx, get_http(), get_runtime_settings())
        lics = await BuscarLicitacionesPorNombre(repo).execute(
            query, fecha_inicio, fecha_fin
        )
        if not lics:
            return {
                "cantidad": 0,
                "licitaciones": [],
                "mensaje": f"No se encontraron licitaciones con '{query}'.",
            }
        return {
            "cantidad": len(lics),
            "licitaciones": [l.model_dump(mode="json") for l in lics],
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def buscar_licitaciones_software(
    query: Optional[str] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
) -> dict[str, Any]:
    """Busca licitaciones relacionadas con desarrollo de software y servicios TI.

    Filtra por códigos UNSPSC de tecnología (prefijos 43, 4323, 81111, 81112)
    y por palabras clave en nombre, descripción y categorías de ítems.
    Retorna resultados ordenados por score de relevancia (0-3).

    Si no se especifican fechas, busca entre las licitaciones activas del día.
    Fechas en formato ddmmaaaa. Rango máximo: 30 días.

    Parámetro 'query' opcional para refinar la búsqueda por texto adicional."""
    try:
        ctx = current_tenant()
        repo = await make_licitacion_repo(ctx, get_http(), get_runtime_settings())
        resultados = await BuscarLicitacionesSoftware(repo).execute(
            query=query,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
        if not resultados:
            return {
                "cantidad": 0,
                "licitaciones": [],
                "mensaje": "No se encontraron licitaciones de software/TI activas hoy.",
            }
        return {
            "cantidad": len(resultados),
            "licitaciones": [
                {
                    "score_relevancia": r["score"],
                    **r["licitacion"].model_dump(mode="json"),
                }
                for r in resultados
            ],
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def filtrar_licitaciones_por_categoria(
    codigos_unspsc: list[str],
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
) -> dict[str, Any]:
    """Filtra licitaciones por prefijos de código UNSPSC en sus ítems.

    Útil para buscar licitaciones de cualquier rubro por categoría de producto.
    Perfiles predefinidos disponibles:
    - software: ['43', '4323', '81111', '81112']
    - construccion: ['72', '73', '7210', '7211']
    - salud: ['42', '85', '8510', '8511']
    - consultoria: ['80', '8010', '8011']
    - educacion: ['86', '8610']

    Fechas en formato ddmmaaaa. Sin fechas, usa las licitaciones activas del día."""
    try:
        ctx = current_tenant()
        repo = await make_licitacion_repo(ctx, get_http(), get_runtime_settings())
        resultados = await BuscarLicitacionesSoftware(repo).execute(
            query=None,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            perfil="software",
        )
        from domain.licitacion.categories import CategoryFilter
        filtradas = [
            r for r in resultados
            if CategoryFilter.matches_unspsc(r["licitacion"], codigos_unspsc)
        ]
        return {
            "cantidad": len(filtradas),
            "prefijos_buscados": codigos_unspsc,
            "licitaciones": [r["licitacion"].model_dump(mode="json") for r in filtradas],
        }
    except Exception as e:
        return {"error": str(e)}


# ─── Órdenes de Compra ───────────────────────────────────────────────────────


@mcp.tool()
async def obtener_orden_compra(codigo: str) -> dict[str, Any]:
    """Obtiene el detalle completo de una orden de compra de Mercado Público por su código.
    Ejemplo de código: '2097-241-SE14'. Retorna todos los campos incluyendo comprador,
    proveedor, ítems con precios y totales."""
    try:
        ctx = current_tenant()
        repo = await make_oc_repo(ctx, get_http(), get_runtime_settings())
        oc = await ObtenerOrdenCompra(repo).execute(codigo)
        return oc.model_dump(mode="json")
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def listar_ordenes_hoy() -> dict[str, Any]:
    """Lista todas las órdenes de compra emitidas en el día actual en todos sus estados."""
    try:
        ctx = current_tenant()
        repo = await make_oc_repo(ctx, get_http(), get_runtime_settings())
        ocs = await ListarOrdenesHoy(repo).execute()
        return {
            "cantidad": len(ocs),
            "ordenes": [o.model_dump(mode="json") for o in ocs],
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def listar_ordenes_por_fecha(fecha: str) -> dict[str, Any]:
    """Lista las órdenes de compra emitidas en una fecha específica.
    El parámetro 'fecha' debe estar en formato ddmmaaaa (ejemplo: '02022014')."""
    try:
        ctx = current_tenant()
        repo = await make_oc_repo(ctx, get_http(), get_runtime_settings())
        ocs = await ListarOrdenesPorFecha(repo).execute(fecha)
        return {
            "cantidad": len(ocs),
            "ordenes": [o.model_dump(mode="json") for o in ocs],
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def listar_ordenes_por_estado(estado: str, fecha: Optional[str] = None) -> dict[str, Any]:
    """Lista órdenes de compra filtradas por estado. Si no se especifica fecha, usa el día actual.
    Estados válidos: enviadaproveedor, aceptada, cancelada, recepcionconforme,
    pendienterecepcion, recepcionaceptadacialmente, recepecionconformeincompleta, todos.
    Fecha en formato ddmmaaaa (opcional)."""
    try:
        ctx = current_tenant()
        repo = await make_oc_repo(ctx, get_http(), get_runtime_settings())
        ocs = await ListarOrdenesPorEstado(repo).execute(estado, fecha)
        return {
            "cantidad": len(ocs),
            "ordenes": [o.model_dump(mode="json") for o in ocs],
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def listar_ordenes_por_organismo(
    codigo_organismo: str, fecha: Optional[str] = None
) -> dict[str, Any]:
    """Lista las órdenes de compra emitidas por un organismo público específico.
    El 'codigo_organismo' es el código numérico del organismo (ejemplo: '6945').
    Fecha en formato ddmmaaaa (opcional, por defecto día actual)."""
    try:
        ctx = current_tenant()
        repo = await make_oc_repo(ctx, get_http(), get_runtime_settings())
        ocs = await ListarOrdenesPorOrganismo(repo).execute(codigo_organismo, fecha)
        return {
            "cantidad": len(ocs),
            "ordenes": [o.model_dump(mode="json") for o in ocs],
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def listar_ordenes_por_proveedor(
    codigo_proveedor: str, fecha: Optional[str] = None
) -> dict[str, Any]:
    """Lista las órdenes de compra enviadas a un proveedor específico.
    El 'codigo_proveedor' es el código numérico del proveedor (ejemplo: '17793').
    Fecha en formato ddmmaaaa (opcional, por defecto día actual)."""
    try:
        ctx = current_tenant()
        repo = await make_oc_repo(ctx, get_http(), get_runtime_settings())
        ocs = await ListarOrdenesPorProveedor(repo).execute(codigo_proveedor, fecha)
        return {
            "cantidad": len(ocs),
            "ordenes": [o.model_dump(mode="json") for o in ocs],
        }
    except Exception as e:
        return {"error": str(e)}


# ─── Helpers de persistencia ─────────────────────────────────────────────────


async def _persist_file_to_storage(local_path: Path, storage_key: str) -> dict[str, Any]:
    """Read the bytes of a locally-generated file and write them to the
    tenant's Storage under `storage_key`. Returns dict with key + signed_url.
    """
    ctx = current_tenant()
    data = local_path.read_bytes()
    await ctx.storage.write_bytes(storage_key, data)
    try:
        url = await ctx.storage.signed_url(storage_key)
    except Exception:
        url = None
    return {"key": storage_key, "url": url, "bytes": len(data)}


# ─── Cotización ──────────────────────────────────────────────────────────────


@mcp.tool()
async def generar_cotizacion_excel(
    codigo: str,
    items_precios: list[dict[str, Any]],
    datos_proveedor: dict[str, Any],
    output_dir: Optional[str] = None,
) -> dict[str, Any]:
    """Genera un archivo Excel de cotización para una licitación de Mercado Público.

    Combina los ítems de la licitación (obtenidos de la API) con los precios
    proporcionados y genera un .xlsx formateado con encabezado, tabla de precios,
    subtotal, IVA, total y bloque de firma.

    Args:
        codigo: Código de la licitación (ej: '1005498-5-LE26')
        items_precios: Lista de dicts con los precios por correlativo.
            Ejemplo: [{"correlativo": 1, "precio_unitario_neto": 150000}, ...]
            Si la licitación no tiene ítems en la API, incluir también
            'descripcion', 'cantidad' y 'unidad_medida' en cada dict.
        datos_proveedor: Dict con datos de la empresa.
        output_dir: (deprecated) Ignorado en multi-tenant; el archivo
            se persiste en el storage del tenant bajo 'ofertas/<codigo>/'.

    Returns:
        Dict con la clave de storage, URL firmada y total de bytes.
    """
    try:
        from application.cotizacion.use_cases import GenerarCotizacionExcel

        ctx = current_tenant()
        repo = await make_licitacion_repo(ctx, get_http(), get_runtime_settings())

        with tempfile.TemporaryDirectory(prefix="mp-cot-") as tmpdir:
            local = await GenerarCotizacionExcel(repo).execute(
                codigo=codigo,
                items_precios=items_precios,
                datos_proveedor=datos_proveedor,
                output_dir=tmpdir,
            )
            key = f"ofertas/{codigo}/cotizacion_{codigo}.xlsx"
            persisted = await _persist_file_to_storage(local, key)

        return {
            "success": True,
            "archivo": persisted["key"],
            "url": persisted["url"],
            "bytes": persisted["bytes"],
            "mensaje": f"Excel generado y persistido en storage del tenant ({persisted['key']}).",
        }
    except Exception as e:
        return {"error": str(e)}


# ─── Documentos de postulación ───────────────────────────────────────────────


@mcp.tool()
async def listar_tipos_documentos() -> dict[str, Any]:
    """Lista todos los tipos de documentos de postulación disponibles para generar.

    Retorna el catálogo completo con nombre, descripción y campos requeridos
    para cada tipo de documento estándar de licitaciones chilenas."""
    from application.documentos.use_cases import ListarTiposDocumentos
    return {"documentos": ListarTiposDocumentos().execute()}


@mcp.tool()
async def generar_documento_licitacion(
    tipo: str,
    codigo: str,
    datos_proveedor: dict[str, Any],
    output_dir: Optional[str] = None,
) -> dict[str, Any]:
    """Genera un documento DOCX de postulación para una licitación específica.

    Args:
        tipo: Tipo de documento. Valores válidos:
            - carta_presentacion
            - anexo_2_aceptacion_bases
            - anexo_3_conflicto_intereses
            - anexo_4_declaracion_probidad
            - anexo_5_datos_transferencia
            - anexo_7_pacto_integridad
        codigo: Código de la licitación (ej: '1005498-5-LE26')
        datos_proveedor: Dict con datos de la empresa.
        output_dir: (deprecated) Ignorado en multi-tenant; el archivo se
            persiste en el storage del tenant bajo
            'ofertas/<codigo>/documentos_postulacion/'.

    Returns:
        Dict con clave de storage, URL firmada y tipo."""
    try:
        from application.documentos.use_cases import GenerarDocumento

        ctx = current_tenant()
        repo = await make_licitacion_repo(ctx, get_http(), get_runtime_settings())

        with tempfile.TemporaryDirectory(prefix="mp-doc-") as tmpdir:
            local = await GenerarDocumento(repo).execute(
                tipo=tipo,
                codigo=codigo,
                datos_proveedor=datos_proveedor,
                output_dir=tmpdir,
            )
            key = f"ofertas/{codigo}/documentos_postulacion/{tipo}.docx"
            persisted = await _persist_file_to_storage(local, key)

        return {
            "success": True,
            "archivo": persisted["key"],
            "url": persisted["url"],
            "tipo": tipo,
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def generar_documentos_licitacion(
    codigo: str,
    datos_proveedor: dict[str, Any],
    output_dir: Optional[str] = None,
) -> dict[str, Any]:
    """Genera todos los documentos estándar de postulación para una licitación.

    Genera en un solo paso: carta de presentación + los 5 anexos estándar.

    Args:
        codigo: Código de la licitación (ej: '1005498-5-LE26')
        datos_proveedor: Dict con datos de la empresa.
        output_dir: (deprecated) Ignorado en multi-tenant; los archivos se
            persisten bajo 'ofertas/<codigo>/documentos_postulacion/'.

    Returns:
        Dict con la lista de claves de storage generadas."""
    try:
        from application.documentos.use_cases import GenerarTodosDocumentos

        ctx = current_tenant()
        repo = await make_licitacion_repo(ctx, get_http(), get_runtime_settings())

        archivos: list[dict[str, Any]] = []
        with tempfile.TemporaryDirectory(prefix="mp-docs-") as tmpdir:
            paths = await GenerarTodosDocumentos(repo).execute(
                codigo=codigo,
                datos_proveedor=datos_proveedor,
                output_dir=tmpdir,
            )
            for local in paths:
                key = f"ofertas/{codigo}/documentos_postulacion/{local.name}"
                persisted = await _persist_file_to_storage(local, key)
                archivos.append(persisted)

        return {
            "success": True,
            "cantidad": len(archivos),
            "archivos": [a["key"] for a in archivos],
            "urls": [a["url"] for a in archivos],
        }
    except Exception as e:
        return {"error": str(e)}


# ─── Perfil de proveedor ─────────────────────────────────────────────────────


CAMPOS_REQUERIDOS_PROFILE = [
    "empresa", "rut", "representante_legal", "direccion", "telefono", "email",
]


@mcp.tool()
async def guardar_perfil_proveedor(datos: dict[str, Any]) -> dict[str, Any]:
    """Guarda el perfil de la empresa en el storage de perfil del tenant.

    Una vez guardado, todas las tools de generación usarán estos datos
    automáticamente sin necesidad de pasarlos en cada llamada.

    Campos requeridos: empresa, rut, representante_legal, direccion, telefono, email.
    Campos opcionales: giro, banco, tipo_cuenta, numero_cuenta, email_transferencia,
    ticket (token ChileCompra para esta empresa)."""
    try:
        ctx = current_tenant()
        faltantes = [c for c in CAMPOS_REQUERIDOS_PROFILE if not datos.get(c)]
        if faltantes:
            return {
                "error": f"Campos requeridos faltantes: {', '.join(faltantes)}",
                "campos_requeridos": CAMPOS_REQUERIDOS_PROFILE,
            }
        existing = await ctx.profile_store.get() or {}
        merged = {**existing, **datos}
        await ctx.profile_store.save(merged)
        return {
            "success": True,
            "tenant_id": ctx.tenant_id,
            "campos": list(merged.keys()),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def obtener_perfil_proveedor() -> dict[str, Any]:
    """Obtiene el perfil de proveedor guardado para el tenant actual.

    Retorna los datos guardados o un mensaje indicando que no hay perfil."""
    try:
        ctx = current_tenant()
        perfil = await ctx.profile_store.get()
        if not perfil:
            return {
                "perfil": None,
                "mensaje": (
                    "No hay perfil guardado para este tenant. "
                    "Usá guardar_perfil_proveedor() para configurarlo."
                ),
                "tenant_id": ctx.tenant_id,
            }
        return {"perfil": perfil, "tenant_id": ctx.tenant_id}
    except Exception as e:
        return {"error": str(e)}


# ─── Orquestación ─────────────────────────────────────────────────────────────
# NOTE (Chunk 2): las orquestadoras (analizar_licitacion_completa y
# preparar_oferta) llaman al scraper y a infrastructure/profile (legacy).
# Migramos la parte API/profile a TenantContext; las llamadas al scraper
# quedan rotas hasta Chunk 3 (scraper refactor).


@mcp.tool()
async def analizar_licitacion_completa(codigo: str) -> dict[str, Any]:
    """Obtiene un análisis completo de una licitación combinando API + documentos.

    Parte API: estructurada vía repo del tenant.
    Parte scraper: queda pendiente para Chunk 3 (BrowserPool + cookies por tenant).

    Args:
        codigo: Código de la licitación (ej: '1005498-5-LE26')"""
    resultado: dict[str, Any] = {"codigo": codigo}

    try:
        ctx = current_tenant()
        repo = await make_licitacion_repo(ctx, get_http(), get_runtime_settings())
        lic = await ObtenerLicitacion(repo).execute(codigo)
        resultado["licitacion"] = lic.model_dump(mode="json")

        from domain.licitacion.categories import CategoryFilter
        resultado["score_software"] = CategoryFilter.score_software(lic)

        if lic.Fechas:
            resultado["fecha_cierre"] = (
                lic.Fechas.FechaCierre.isoformat() if lic.Fechas.FechaCierre else None
            )
        resultado["monto_estimado"] = lic.MontoEstimado
        resultado["organismo"] = (
            lic.Comprador.NombreOrganismo if lic.Comprador else None
        )
    except Exception as e:
        resultado["error_api"] = str(e)
        return resultado

    # Documentos del scraper (Chunk 3): tenant-scoped via ScraperRepo.
    try:
        from interfaces.mcp.runtime import RuntimeNotReadyError, get_browser_pool

        try:
            pool = get_browser_pool()
        except RuntimeNotReadyError:
            pool = None
        scraper = make_scraper_repo(ctx, pool)
        resultado["documentos"] = await scraper.descargar_documentacion(codigo)
    except Exception as exc:  # noqa: BLE001
        resultado["documentos"] = {
            "disponible": False,
            "error": str(exc),
        }
    return resultado


@mcp.tool()
async def preparar_oferta(
    codigo: str,
    items_precios: list[dict[str, Any]],
    datos_proveedor: Optional[dict[str, Any]] = None,
    output_dir: Optional[str] = None,
) -> dict[str, Any]:
    """Genera el paquete completo de postulación para una licitación.

    Genera la cotización Excel + todos los DOCX y los persiste en el storage
    del tenant bajo 'ofertas/<codigo>/'.

    Args:
        codigo: Código de la licitación (ej: '1005498-5-LE26')
        items_precios: Lista de precios por correlativo.
        datos_proveedor: Dict opcional. Si no se pasa, se usa el perfil
            del tenant; si se pasa, se mergea sobre el perfil.
        output_dir: (deprecated) Ignorado; persistencia va al storage del tenant.
    """
    try:
        from application.cotizacion.use_cases import GenerarCotizacionExcel
        from application.documentos.use_cases import GenerarTodosDocumentos

        ctx = current_tenant()
        perfil = await ctx.profile_store.get() or {}
        datos = {**perfil, **(datos_proveedor or {})}
        if not datos.get("empresa"):
            return {
                "error": (
                    "No hay perfil de proveedor para este tenant. "
                    "Usá guardar_perfil_proveedor() primero o pasá datos_proveedor."
                ),
            }

        repo = await make_licitacion_repo(ctx, get_http(), get_runtime_settings())

        archivos: list[dict[str, Any]] = []
        with tempfile.TemporaryDirectory(prefix="mp-oferta-") as tmpdir:
            base = Path(tmpdir)

            excel_local = await GenerarCotizacionExcel(repo).execute(
                codigo=codigo,
                items_precios=items_precios,
                datos_proveedor=datos,
                output_dir=str(base),
            )
            excel_persisted = await _persist_file_to_storage(
                excel_local, f"ofertas/{codigo}/cotizacion_{codigo}.xlsx"
            )
            archivos.append({"tipo": "cotizacion", **excel_persisted})

            docs_dir = base / "documentos_postulacion"
            docx_locals = await GenerarTodosDocumentos(repo).execute(
                codigo=codigo,
                datos_proveedor=datos,
                output_dir=str(docs_dir),
            )
            for local in docx_locals:
                persisted = await _persist_file_to_storage(
                    local,
                    f"ofertas/{codigo}/documentos_postulacion/{local.name}",
                )
                archivos.append({"tipo": "docx", **persisted})

        return {
            "success": True,
            "codigo": codigo,
            "tenant_id": ctx.tenant_id,
            "total_archivos": len(archivos),
            "archivos": [a["key"] for a in archivos],
            "urls": [a["url"] for a in archivos],
            "siguiente_paso": (
                "Revisá los documentos, completá los campos marcados con ___ "
                "y cargalos al portal de Mercado Público."
            ),
        }
    except Exception as e:
        return {"error": str(e)}


# ─── Importar tools del scraper de documentos (opcional) ─────────────────────
# Estas tools permiten descargar documentos anexos desde el portal web.
# Chunk 3 las migrará a TenantContext; por ahora se importan tal cual.
try:
    from interfaces.mcp.scraper_tools import (  # noqa: F401
        descargar_documentacion_licitacion,
        obtener_info_licitacion_con_documentos,
        verificar_sesion_scraper,
    )
except ImportError:
    pass
