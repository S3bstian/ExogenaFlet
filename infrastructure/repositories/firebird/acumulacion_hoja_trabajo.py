"""Acumulacion masiva en HOJA_TRABAJO (Firebird).

El vaciado previo por concepto en la misma transaccion usa
``hoja_trabajo_persistencia.delete_hoja_trabajo_por_id_concepto_cursor``.
"""
import time
from collections import defaultdict
from threading import Event
from typing import Any, Dict, List, Optional, Tuple

from infrastructure.persistence.firebird.hoja_trabajo_persistencia import (
    TABLAS_CUENTAS_PERMITIDAS,
    TABLAS_MOVIMIENTOS_PERMITIDAS,
    delete_hoja_trabajo_por_id_concepto_cursor,
    insert_fila_hoja_trabajo,
    resolver_id_concepto_legacy,
)
from infrastructure.adapters.proteccion_firebird import proceso_protegido, transaccion_segura

from domain.entities.resultado_acumulacion import (
    AdvertenciaAcumulacionSinDatos,
    ResultadoAcumulacion,
)

_ACUMULAR_CANCEL_MSG = "__ACUMULAR_CANCEL__"


def _normalizar_tipo_elemento(raw: Any) -> str:
    """Devuelve T/C/B/A en mayúscula; la BD puede devolver distinta capitalización o bytes."""
    if raw is None:
        return ""
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("ascii", errors="ignore")
    s = str(raw).strip()
    return s[:1].upper() if s else ""


def _codigo_cuenta_no_vacio(valor: Any) -> bool:
    """True si el código de cuenta del atributo existe y no es solo espacios."""
    return valor is not None and str(valor).strip() != ""


def _safe_sum(acc: float, val: Any) -> float:
    """Suma segura para acumulaciones numéricas tolerando None/valores no numéricos."""
    if val is None:
        return acc
    try:
        return acc + float(val)
    except (TypeError, ValueError):
        return acc


def _get_or_default(row: Any, idx: int, default: Any) -> Any:
    """Retorna `row[idx]` cuando existe; de lo contrario `default`."""
    return row[idx] if idx < len(row) else default


def _agrupar_por_identidad(setsdatos: List[Tuple[Any, ...]], idx_identidad: int) -> Dict[Any, List[Tuple[Any, ...]]]:
    """Agrupa filas por identidad usando el índice indicado."""
    grupos: Dict[Any, List[Tuple[Any, ...]]] = defaultdict(list)
    for row in setsdatos:
        grupos[_get_or_default(row, idx_identidad, "")].append(row)
    return grupos


def _unificar_tipo_t(setsdatos: List[Tuple[Any, ...]]) -> Tuple[List[Tuple[Any, ...]], Dict[Any, Dict[str, Any]]]:
    """Unifica filas tipo T por identidad sumando campos monetarios."""
    grupos = _agrupar_por_identidad(setsdatos, 1)
    merged: List[Tuple[Any, ...]] = []
    info: Dict[Any, Dict[str, Any]] = {}
    for identidad, filas in grupos.items():
        if len(filas) > 1:
            info[identidad] = {
                "cantidad": len(filas),
                "valores_antes": {
                    "saldoinicial": [f[idx] for f in filas for idx in [13]],
                    "debitos": [f[idx] for f in filas for idx in [14]],
                    "creditos": [f[idx] for f in filas for idx in [15]],
                    "neto": [f[idx] for f in filas for idx in [16]],
                    "saldofinal": [f[idx] for f in filas for idx in [17]],
                },
            }
        base = list(filas[0])
        for idx in (13, 14, 15, 16, 17):
            base[idx] = 0
            for fila in filas:
                base[idx] = _safe_sum(base[idx], fila[idx])
        merged.append(tuple(base))
    return merged, info


def _unificar_tipo_b(setsdatos: List[Tuple[Any, ...]]) -> Tuple[List[Tuple[Any, ...]], Dict[Any, Dict[str, Any]]]:
    """Unifica filas tipo B por identidad sumando saldo."""
    grupos = _agrupar_por_identidad(setsdatos, 0)
    merged: List[Tuple[Any, ...]] = []
    info: Dict[Any, Dict[str, Any]] = {}
    for identidad, filas in grupos.items():
        if len(filas) > 1:
            info[identidad] = {
                "cantidad": len(filas),
                "valores_antes": {"saldo": [f[3] for f in filas]},
            }
        base = list(filas[0])
        base[3] = 0
        for fila in filas:
            base[3] = _safe_sum(base[3], fila[3])
        merged.append(tuple(base))
    return merged, info


def _unificar_tipo_a(setsdatos: List[Tuple[Any, ...]]) -> Tuple[List[Tuple[Any, ...]], Dict[Any, Dict[str, Any]]]:
    """Unifica filas tipo A por tercero sumando saldos y movimientos."""
    grupos = _agrupar_por_identidad(setsdatos, 3)
    merged: List[Tuple[Any, ...]] = []
    info: Dict[Any, Dict[str, Any]] = {}
    for identidad, filas in grupos.items():
        if len(filas) > 1:
            info[identidad] = {
                "cantidad": len(filas),
                "valores_antes": {
                    "SaldoInicial": [f[idx] for f in filas for idx in [4]],
                    "Debitos": [f[idx] for f in filas for idx in [5]],
                    "Creditos": [f[idx] for f in filas for idx in [6]],
                    "SaldoFinal": [f[idx] for f in filas for idx in [7]],
                },
            }
        base = list(filas[0])
        for idx in (4, 5, 6, 7):
            base[idx] = 0
            for fila in filas:
                base[idx] = _safe_sum(base[idx], fila[idx])
        merged.append(tuple(base))
    return merged, info


def _unificar_setsdatos_por_tipo(
    tipo_el: str,
    setsdatos: List[Tuple[Any, ...]],
) -> Tuple[List[Tuple[Any, ...]], Dict[Any, Dict[str, Any]]]:
    """Unifica sets por tipo de elemento y retorna datos unificados + detalle de duplicados."""
    if tipo_el == "T":
        return _unificar_tipo_t(setsdatos)
    if tipo_el == "B":
        return _unificar_tipo_b(setsdatos)
    if tipo_el == "A":
        return _unificar_tipo_a(setsdatos)
    return setsdatos, {}


def _obtener_idtercero_por_tipo(tipo_el: str, setdatos: Tuple[Any, ...]) -> Any:
    """Obtiene identidad/tercero según la estructura del tipo de elemento."""
    if tipo_el == "T":
        return _get_or_default(setdatos, 1, "")
    if tipo_el == "B":
        return _get_or_default(setdatos, 0, "")
    if tipo_el == "A":
        return _get_or_default(setdatos, 3, "")
    tercero = _get_or_default(setdatos, 3, "")
    return tercero if tercero else _get_or_default(setdatos, 0, "")


def _resolver_valor_atributo(
    tipo_el: str,
    attr: Tuple[Any, ...],
    setdatos: Tuple[Any, ...],
    concepto_codigo: Any,
    set_idx: int,
) -> Any:
    """Resuelve el valor del atributo según reglas de acumulado y tipo de elemento."""
    sin_valor = "Sin valor"
    tipo_acumulado = None if attr[5] in {2, 3} else attr[1]

    match tipo_acumulado:
        case None:
            return "Sin Valor"
        case 50:
            return _get_or_default(setdatos, 0, sin_valor) if tipo_el == "A" else sin_valor
        case 31:
            return _get_or_default(setdatos, 15, sin_valor) if tipo_el == "T" else sin_valor
        case x if x in (1010, 1023, 1067):
            return _get_or_default(setdatos, 10, sin_valor) if tipo_el == "T" else sin_valor
        case x if x in (1011, 1024, 1068):
            return _get_or_default(setdatos, 11, sin_valor) if tipo_el == "T" else sin_valor
        case 1001:
            return concepto_codigo
        case 3:
            if tipo_el == "T":
                return _get_or_default(setdatos, 15, sin_valor)
            if tipo_el in ("C", "A"):
                return _get_or_default(setdatos, 6, sin_valor)
            return sin_valor
        case x if x in (1014, 1052):
            return _get_or_default(setdatos, 10, sin_valor) if tipo_el == "T" else sin_valor
        case 2:
            if tipo_el == "T":
                return _get_or_default(setdatos, 14, sin_valor)
            if tipo_el in ("C", "A"):
                return _get_or_default(setdatos, 5, sin_valor)
            return sin_valor
        case x if x in (1013, 1026):
            if tipo_el == "T":
                return _get_or_default(setdatos, 3, sin_valor)
            if tipo_el == "B":
                return _get_or_default(setdatos, 2, sin_valor)
            return sin_valor
        case x if x in (1009, 1051):
            return _get_or_default(setdatos, 9, sin_valor) if tipo_el == "T" else sin_valor
        case 1071:
            if tipo_el == "T":
                return _get_or_default(setdatos, 1, sin_valor)
            if tipo_el == "B":
                return _get_or_default(setdatos, 0, sin_valor)
            return sin_valor
        case 61:
            if tipo_el == "T":
                return _get_or_default(setdatos, 15, sin_valor)
            if tipo_el == "C":
                return _get_or_default(setdatos, 6, sin_valor)
            return sin_valor
        case 62:
            if tipo_el == "T":
                return _get_or_default(setdatos, 14, sin_valor)
            if tipo_el == "C":
                return _get_or_default(setdatos, 5, sin_valor)
            return sin_valor
        case x if x in (1015, 1053):
            return _get_or_default(setdatos, 11, sin_valor) if tipo_el == "T" else sin_valor
        case x if x in (4, 14):
            if tipo_el == "T":
                return _get_or_default(setdatos, 16, sin_valor)
            if tipo_el == "C":
                return _get_or_default(setdatos, 7, sin_valor)
            return sin_valor
        case 1072:
            return sin_valor
        case x if x in (1003, 1017, 1041, 1046, 1056, 1073):
            if tipo_el == "T":
                return _get_or_default(setdatos, 1, sin_valor)
            if tipo_el == "B":
                return _get_or_default(setdatos, 0, sin_valor)
            return sin_valor
        case x if x in (1007, 1021, 1030, 1035, 1040, 1043, 1050, 1060, 1065):
            return _get_or_default(setdatos, 8, "") if tipo_el == "T" else ""
        case x if x in (1012, 1025, 1054, 1069):
            return _get_or_default(setdatos, 12, sin_valor) if tipo_el == "T" else sin_valor
        case x if x in (1004, 1018, 1027, 1032, 1037, 1047, 1057, 1062):
            return _get_or_default(setdatos, 5, "") if tipo_el == "T" else ""
        case x if x in (1006, 1020, 1029, 1034, 1039, 1042, 1049, 1059, 1064):
            return _get_or_default(setdatos, 7, "") if tipo_el == "T" else ""
        case x if x in (1008, 1022, 1031, 1036, 1044, 1061, 1066):
            return _get_or_default(setdatos, 4, "") if tipo_el == "T" else ""
        case 15:
            return _get_or_default(setdatos, 8, sin_valor) if tipo_el == "C" else sin_valor
        case 5:
            return _get_or_default(setdatos, 17, sin_valor) if tipo_el == "T" else sin_valor
        case x if x in (1, 11):
            if tipo_el == "T":
                return _get_or_default(setdatos, 13, sin_valor)
            if tipo_el in ("C", "A"):
                return _get_or_default(setdatos, 4, sin_valor)
            return sin_valor
        case 21:
            return _get_or_default(setdatos, 3, sin_valor) if tipo_el == "B" else sin_valor
        case x if x in (1005, 1019, 1028, 1033, 1038, 1048, 1058, 1063):
            return _get_or_default(setdatos, 6, "") if tipo_el == "T" else ""
        case x if x in (1002, 1016, 1045, 1055, 1070):
            return _get_or_default(setdatos, 0, sin_valor) if tipo_el == "T" else sin_valor
        case 51:
            return _get_or_default(setdatos, 0, sin_valor) if tipo_el == "A" else sin_valor
        case _:
            if (set_idx + 1) % 500 == 0:
                print(f"    [WARNING] Caso no mapeado - ID: {attr[1]}, Desc: {attr[3][:30]}..., Tipo: {tipo_el}")
            return 0


def _tabla_por_tipocontabilidad(tipo_contabilidad: Any) -> str:
    """Mapea tipo de contabilidad a sufijo de tabla dinámica."""
    if tipo_contabilidad == 1:
        return "_trib"
    if tipo_contabilidad == 2:
        return "_cont"
    return ""


def _agregar_rows_con_identidad(
    datos: List[Tuple[Any, ...]],
    idx_identidad: int,
    setsdatos: List[Tuple[Any, ...]],
    identidades_unicas_antes: set,
) -> int:
    """Acumula rows y registra identidades únicas detectadas; retorna cantidad añadida."""
    setsdatos.extend(datos)
    for row in datos:
        identidad = _get_or_default(row, idx_identidad, "")
        if identidad:
            identidades_unicas_antes.add(identidad)
    return len(datos)


def _cargar_sets_tipo_b(cur: Any, setsdatos: List[Tuple[Any, ...]], identidades_unicas_antes: set) -> int:
    """Carga sets para elemento tipo B y acumula identidades por fila."""
    query = """SELECT 
            Identidad, Nombre, Verificacion, Saldo 
        FROM BANCOS_MOV
    """
    cur.execute(query)
    datos = cur.fetchall()
    return _agregar_rows_con_identidad(datos, 0, setsdatos, identidades_unicas_antes)


def _cargar_sets_tipo_a(
    cur: Any,
    tabla: str,
    setsdatos: List[Tuple[Any, ...]],
    identidades_unicas_antes: set,
) -> int:
    """Carga sets para elemento tipo A y acumula identidades por tercero."""
    query = f"""SELECT 
            Codigo, Nombre, Naturaleza, Tercero, SaldoInicial, Debitos, 
            Creditos, SaldoFinal, ValorAbsoluto 
        FROM cuentas{tabla}
    """
    cur.execute(query)
    datos = cur.fetchall()
    return _agregar_rows_con_identidad(datos, 3, setsdatos, identidades_unicas_antes)


def _registrar_error_insert(
    total_errores: List[Dict[str, Any]],
    concepto_codigo: Any,
    set_idx: int,
    attr: Tuple[Any, ...],
    id_limpio: str,
    error: Exception,
) -> None:
    """Construye y registra un error de inserción para trazabilidad y UI."""
    error_info = {
        "concepto": concepto_codigo,
        "set": set_idx + 1,
        "atributo_id": attr[0],
        "atributo_desc": attr[3][:40],
        "identidad": id_limpio,
        "error": str(error),
    }
    total_errores.append(error_info)
    print(f"[ERROR] Concepto {concepto_codigo}, Set {set_idx + 1}, Atributo {attr[0]}: {error}")


def _imprimir_resumen_concepto(
    concepto_codigo: Any,
    total_sets: int,
    insert_count: int,
    inserts_detallados: int,
) -> None:
    """Imprime resumen de inserciones por concepto."""
    if insert_count > 0:
        if inserts_detallados < insert_count:
            print(
                f"[ACUMULACIÓN]   Concepto {concepto_codigo}: {total_sets} set(s) → {insert_count} "
                f"insert(s) (detalle de los primeros {min(inserts_detallados, insert_count)})"
            )
        else:
            print(f"[ACUMULACIÓN]   Concepto {concepto_codigo}: {total_sets} set(s) → {insert_count} insert(s)")
        return
    print(f"[ACUMULACIÓN]   Concepto {concepto_codigo}: {total_sets} set(s) → 0 insert(s)")


def _insertar_sets_concepto(
    cur: Any,
    setsdatos: List[Tuple[Any, ...]],
    atributos: List[Tuple[Any, ...]],
    tipo_el: str,
    concepto: Dict[str, Any],
    elemento_id: Any,
    concepto_codigo: Any,
    concepto_actual: int,
    total_conceptos: int,
    log_max_sets_detalle: int,
    log_max_inserts_detalle: int,
    total_errores: List[Dict[str, Any]],
    en_ui: Any,
    raise_if_cancel: Any,
) -> int:
    """Inserta filas de un concepto en HOJA_TRABAJO y retorna cantidad insertada."""
    total_sets = len(setsdatos)
    insert_count = 0
    inserts_detallados = 0

    for i, setdatos in enumerate(setsdatos):
        raise_if_cancel()
        contattr = []
        mostrar_detalle_set = total_sets <= log_max_sets_detalle or i < log_max_sets_detalle

        for idx_attr, attr in enumerate(atributos):
            if idx_attr % 16 == 0:
                raise_if_cancel()
            if attr[0] in contattr:
                continue

            valor = _resolver_valor_atributo(
                tipo_el=tipo_el,
                attr=attr,
                setdatos=setdatos,
                concepto_codigo=concepto.get("codigo"),
                set_idx=i,
            )
            idtercero = _obtener_idtercero_por_tipo(tipo_el, setdatos)
            contattr.append(attr[0])
            id_limpio = str(idtercero).strip() if idtercero else ""

            try:
                insert_fila_hoja_trabajo(
                    cur,
                    concepto.get("id"),
                    attr[0],
                    elemento_id,
                    valor,
                    idtercero,
                )
                insert_count += 1
                if mostrar_detalle_set and inserts_detallados < log_max_inserts_detalle:
                    desc = (attr[3][:25] + "…") if len(attr[3]) > 25 else attr[3]
                    val_str = str(valor)[:20] + "…" if valor and len(str(valor)) > 20 else str(valor)
                    print(
                        f"[ACUMULACIÓN]   Insert concepto={concepto_codigo} elem={tipo_el} "
                        f"attr={attr[0]} \"{desc}\" valor={val_str} identidad={id_limpio or '-'}"
                    )
                    inserts_detallados += 1
            except Exception as e:
                _registrar_error_insert(total_errores, concepto_codigo, i, attr, id_limpio, e)

        if (i + 1) % 25 == 0 or (i + 1) == total_sets:
            if total_sets > 0:
                en_ui(0.33 + 0.67 * (i + 1) / total_sets, f"Concepto {concepto_actual} de {total_conceptos}")
            raise_if_cancel()
            time.sleep(0.03)

    _imprimir_resumen_concepto(concepto_codigo, total_sets, insert_count, inserts_detallados)
    return insert_count


def _obtener_elemento_concepto(cur: Any, concepto_id: Any) -> Optional[Tuple[Any, ...]]:
    """Obtiene el elemento activo asociado al concepto."""
    cur.execute(
        """
            SELECT id, tipoacumuladog
            FROM ELEMENTOS
            WHERE idconcepto = ? AND TIPOACUMULADOG <> 'NULL'
        """,
        (concepto_id,),
    )
    return cur.fetchone()


def _obtener_atributos_elemento(cur: Any, elemento_id: Any) -> List[Tuple[Any, ...]]:
    """Obtiene atributos configurados para el elemento, con cuenta asociada cuando existe."""
    cur.execute(
        """
            SELECT
                a.id, 
                a.tipoacumulado, 
                a.tipocontabilidad, 
                a.descripcion, 
                CASE 
                    WHEN a.tipocontabilidad = 1 THEN ct.codigo
                    WHEN a.tipocontabilidad = 2 THEN cc.codigo
                    ELSE NULL
                END AS codigo,
                a.clase
            FROM ATRIBUTOS a
            LEFT JOIN CUENTAS_ATRIBUTOS r ON r.idatributo = a.id
            LEFT JOIN CUENTAS_TRIB ct
                ON (a.tipocontabilidad = 1 AND ct.id = r.idcuenta)
            LEFT JOIN CUENTAS_CONT cc
                ON (a.tipocontabilidad = 2 AND cc.id = r.idcuenta)
            WHERE a.idelemento = ?
            ORDER BY a.id
        """,
        (elemento_id,),
    )
    return cur.fetchall()


def acumular_conceptos_hoja_trabajo(
    conceptos: List[Dict[str, Any]],
    loader: Any,
    page: Any,
    bottom_text: Any,
    cancel_event: Optional[Event] = None,
) -> ResultadoAcumulacion:
    """
    Acumula datos de conceptos en la hoja de trabajo.
    
    Procesa múltiples conceptos, obteniendo elementos, atributos y datos relacionados
    para insertarlos en la hoja de trabajo. Protegido contra ejecuciones simultáneas
    y con transacción atómica.
    
    Parameters
    ----------
    conceptos : List[Dict[str, Any]]
        Lista de diccionarios con información de conceptos. Cada concepto debe tener:
        - 'id': ID del concepto
        - 'codigo': Código del concepto
    loader : Any
        Control de progreso de Flet (ft.ProgressRing o similar) para mostrar avance.
    page : Any
        Página de Flet (ft.Page) para actualizar la UI.
    bottom_text : Any
        Control de texto de Flet (ft.Text) para mostrar mensajes de progreso.
    cancel_event : Optional[Event]
        Si se establece (is_set), se aborta en preparación o entre pasos del concepto y se revierte
        toda la transacción (incluidos los DELETE previos a insertar).
    
    Returns
    -------
    ResultadoAcumulacion
        Estado detallado (inserciones, advertencias por cuenta sin datos, errores, cancelación).
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
    
    Notes
    -----
    Esta función es muy compleja y procesa múltiples tipos de elementos:
    - Tipo 'T': Terceros con movimientos
    - Tipo 'C': Cuentas
    - Tipo 'B': Bancos
    - Tipo 'A': Activos fijos
    
    La función usa whitelist para nombres de tablas dinámicas para prevenir
    inyecciones SQL en queries que construyen nombres de tablas.
    """
    LOG_MAX_ATRIBUTOS = 8
    LOG_MAX_INSERTS_DETALLE = 3
    LOG_MAX_SETS_DETALLE = 2

    from utils.ui_sync import actualizar_progreso_ui

    def en_ui(valor=None, texto=None):
        """Actualiza loader/texto en el hilo de la UI (necesario desde thread)."""
        actualizar_progreso_ui(
            loader, valor=valor, page=page,
            texto_control=bottom_text, texto_valor=texto,
        )

    def _raise_if_cancel() -> None:
        """Aborta en caliente si el usuario pulsó Cancelar (no solo entre conceptos)."""
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError(_ACUMULAR_CANCEL_MSG)

    # Proteger contra ejecuciones simultáneas
    with proceso_protegido("acumular", f"{len(conceptos)} concepto(s)"):
        # Envolver todo en una transacción única
        try:
            with transaccion_segura() as (con, cur):
                setsdatos = []
                
                # --- contador para el bottomsheet ---
                total_conceptos = len(conceptos)
                concepto_actual = 0
                total_inserts = 0
                total_errores = []
                identidades_unificadas_global = 0
                advertencias_sin_datos_map: Dict[Tuple[str, str], set] = defaultdict(set)
                conceptos_omitidos_sin_elemento: List[str] = []
                conceptos_sin_cuentas_en_config: List[str] = []
                conceptos_sin_filas_en_hoja: List[str] = []

                # Vacía HOJA_TRABAJO por concepto en esta misma transacción; al cancelar o fallar,
                # el rollback restaura también lo borrado aquí.
                for prep_idx, concepto_prep in enumerate(conceptos, start=1):
                    _raise_if_cancel()
                    en_ui(
                        min(0.08, 0.01 + 0.07 * prep_idx / max(total_conceptos, 1)),
                        f"Preparando hoja {prep_idx} de {total_conceptos}",
                    )
                    id_prep = resolver_id_concepto_legacy(concepto_prep)
                    if id_prep is None:
                        print(f"Concepto no encontrado: {concepto_prep}")
                    else:
                        delete_hoja_trabajo_por_id_concepto_cursor(cur, id_prep)

                # --------------------------- LOOP PRINCIPAL ---------------------------
                for concepto in conceptos:
                    _raise_if_cancel()
                    concepto_actual += 1
                    en_ui(texto=f"Concepto {concepto_actual} de {total_conceptos}")

                    setsdatos.clear()
                    concepto_codigo = concepto.get("codigo", "N/A")
                    concepto_id = concepto.get("id", "N/A")
                    concepto_formato = concepto.get("formato", "N/A")

                    # -------------------- PASO 1: elemento --------------------
                    try:
                        elemento = _obtener_elemento_concepto(cur, concepto.get("id"))
                        if not elemento:
                            print(f"[WARNING] Concepto {concepto_codigo} omitido: no tiene elemento válido")
                            conceptos_omitidos_sin_elemento.append(str(concepto_codigo))
                            continue
                        tipo_el = _normalizar_tipo_elemento(elemento[1])
                        print(
                            f"[ACUMULACIÓN] Concepto {concepto_codigo} | Formato {concepto_formato} "
                            f"| Elemento id={elemento[0]} tipo={tipo_el}"
                        )
                    except Exception as e:
                        print(f"[ERROR] Concepto {concepto_codigo}: {e}")
                        raise e

                    en_ui(0.11)
                    _raise_if_cancel()
                    time.sleep(0.03)

                    # -------------------- PASO 2: atributos --------------------
                    try:
                        atributos = _obtener_atributos_elemento(cur, elemento[0])
                    except Exception as e:
                        print(f"[ERROR] Obteniendo atributos para concepto {concepto_codigo}: {e}")
                        raise e

                    # Log: lista de atributos (resumida para no saturar)
                    print(f"[ACUMULACIÓN]   Atributos ({len(atributos)}): {atributos}")
                    en_ui(0.22)
                    _raise_if_cancel()
                    time.sleep(0.03)

                    if tipo_el in ("T", "C") and not any(
                        attr[2] in (1, 2) and _codigo_cuenta_no_vacio(attr[4]) for attr in atributos
                    ):
                        conceptos_sin_cuentas_en_config.append(str(concepto_codigo))

                    # -------------------- PASO 3: sets de cuentas --------------------
                    attr_count = 0
                    total_registros_antes_unificar = 0
                    identidades_unicas_antes = set()
                    
                    for attr in atributos:
                        _raise_if_cancel()
                        attr_count += 1
                        try:
                            tabla = _tabla_por_tipocontabilidad(attr[2])

                            # Validar tabla contra whitelist
                            if tabla not in TABLAS_MOVIMIENTOS_PERMITIDAS:
                                print(f"    [WARNING] Atributo {attr_count}: Tabla no permitida '{tabla}', saltando...")
                                continue
                                
                            if tipo_el == "T" and tabla != "" and _codigo_cuenta_no_vacio(attr[4]):
                                tabla_cuentas = "cuentas_trib" if attr[2] == 1 else "cuentas_cont"
                                
                                if tabla_cuentas not in TABLAS_CUENTAS_PERMITIDAS:
                                    continue
                                
                                query = f"""
                                    SELECT 
                                        t.tipodocumento, tm.identidad, t.naturaleza, t.digitoverificacion, t.razonsocial,
                                        t.primerapellido, t.segundoapellido, t.primernombre, t.segundonombre, t.direccion, 
                                        t.departamento, t.municipio, t.pais,
                                        CASE 
                                            WHEN c.valorabsoluto = 'S' THEN ABS(SUM(tm.saldoinicial))
                                            ELSE SUM(tm.saldoinicial)
                                        END AS saldoinicial,
                                        CASE 
                                            WHEN c.valorabsoluto = 'S' THEN ABS(SUM(tm.debitos))
                                            ELSE SUM(tm.debitos)
                                        END AS debitos,
                                        CASE 
                                            WHEN c.valorabsoluto = 'S' THEN ABS(SUM(tm.creditos))
                                            ELSE SUM(tm.creditos)
                                        END AS creditos,
                                        CASE 
                                            WHEN c.valorabsoluto = 'S' THEN ABS(
                                                CASE 
                                                    WHEN t.naturaleza = 0 THEN SUM(tm.debitos) - SUM(tm.creditos)
                                                    ELSE SUM(tm.creditos) - SUM(tm.debitos)
                                                END
                                            )
                                            ELSE 
                                                CASE 
                                                    WHEN t.naturaleza = 0 THEN SUM(tm.debitos) - SUM(tm.creditos)
                                                    ELSE SUM(tm.creditos) - SUM(tm.debitos)
                                                END
                                        END AS neto,
                                        CASE 
                                            WHEN c.valorabsoluto = 'S' THEN ABS(SUM(tm.saldofinal))
                                            ELSE SUM(tm.saldofinal)
                                        END AS saldofinal
                                    FROM TERCEROS t
                                    INNER JOIN TERCEROS_MOV{tabla} tm 
                                            ON tm.identidad = t.identidad
                                    INNER JOIN {tabla_cuentas} c
                                            ON c.codigo = tm.cuenta
                                    WHERE tm.cuenta = ?
                                    GROUP BY 
                                        tm.identidad, t.tipodocumento, t.naturaleza, t.digitoverificacion, t.razonsocial,
                                        t.primerapellido, t.segundoapellido, t.primernombre, t.segundonombre,
                                        t.direccion, t.departamento, t.municipio, t.pais, c.valorabsoluto
                                """
                                
                                cur.execute(query, (attr[4],))
                                datos = cur.fetchall()
                                if not datos and _codigo_cuenta_no_vacio(attr[4]):
                                    advertencias_sin_datos_map[
                                        (str(concepto_codigo), str(concepto_formato))
                                    ].add(str(attr[4]).strip())
                                total_registros_antes_unificar += _agregar_rows_con_identidad(
                                    datos,
                                    1,
                                    setsdatos,
                                    identidades_unicas_antes,
                                )
                            elif tipo_el == "C" and tabla != "":
                                if not _codigo_cuenta_no_vacio(attr[4]):
                                    continue
                                query = f"""
                                    SELECT 
                                        codigo,
                                        nombre,
                                        naturaleza,
                                        tercero,
                                        saldoinicial,
                                        debitos,
                                        creditos,
                                        CASE 
                                            WHEN naturaleza = 'D' THEN debitos - creditos
                                            ELSE creditos - debitos
                                        END AS neto,
                                        saldofinal
                                    FROM CUENTAS{tabla}
                                    WHERE codigo = ?
                                """
                                
                                cur.execute(query, (attr[4],))
                                datos = cur.fetchone()
                                if not datos and _codigo_cuenta_no_vacio(attr[4]):
                                    advertencias_sin_datos_map[
                                        (str(concepto_codigo), str(concepto_formato))
                                    ].add(str(attr[4]).strip())
                                elif datos:
                                    setsdatos.append(datos)
                            elif tipo_el == "B":
                                total_registros_antes_unificar += _cargar_sets_tipo_b(
                                    cur,
                                    setsdatos,
                                    identidades_unicas_antes,
                                )
                            elif tipo_el == "A":
                                total_registros_antes_unificar += _cargar_sets_tipo_a(
                                    cur,
                                    tabla,
                                    setsdatos,
                                    identidades_unicas_antes,
                                )
                        except Exception as e:
                            print(f"[ERROR] Concepto {concepto_codigo}, Atributo {attr[0]}: {e}")
                            raise e

                    en_ui(0.33)
                    _raise_if_cancel()
                    time.sleep(0.03)

                    # ==================== UNIFICACIÓN ====================
                    _raise_if_cancel()
                    identidades_unificadas = {}
                    if tipo_el in ('T', 'B', 'A') and setsdatos:
                        duplicados = total_registros_antes_unificar - len(identidades_unicas_antes)
                        if duplicados > 0:
                            # Solo mostrar si hay duplicados significativos
                            pass  # Info silenciosa, solo se muestra en resumen si es relevante

                    if tipo_el in ('T', 'B', 'A') and setsdatos:
                        setsdatos, identidades_unificadas = _unificar_setsdatos_por_tipo(tipo_el, setsdatos)

                        # Guardar info de unificación para resumen final
                        if identidades_unificadas:
                            identidades_unificadas_global += len(identidades_unificadas)

                    # -------------------- PASO 4: insertar HOJA_TRABAJO --------------------
                    insert_count = _insertar_sets_concepto(
                        cur=cur,
                        setsdatos=setsdatos,
                        atributos=atributos,
                        tipo_el=tipo_el,
                        concepto=concepto,
                        elemento_id=elemento[0],
                        concepto_codigo=concepto_codigo,
                        concepto_actual=concepto_actual,
                        total_conceptos=total_conceptos,
                        log_max_sets_detalle=LOG_MAX_SETS_DETALLE,
                        log_max_inserts_detalle=LOG_MAX_INSERTS_DETALLE,
                        total_errores=total_errores,
                        en_ui=en_ui,
                        raise_if_cancel=_raise_if_cancel,
                    )

                    total_inserts += insert_count
                    if insert_count == 0 and len(conceptos_sin_filas_en_hoja) < 40:
                        conceptos_sin_filas_en_hoja.append(str(concepto_codigo))

                # ==================== RESUMEN FINAL ====================
                print(f"\n[ACUMULACIÓN] Completado: {total_conceptos} concepto(s), {total_inserts} insert(s)")
                if identidades_unificadas_global > 0:
                    print(f"[ACUMULACIÓN] {identidades_unificadas_global} identidad(es) unificada(s)")
                if total_errores:
                    print(f"[WARNING] {len(total_errores)} error(es) durante la inserción")
                    for err in total_errores[:5]:  # Mostrar solo primeros 5 errores
                        print(f"  - {err['concepto']}, Atributo {err['atributo_id']}: {err['error'][:60]}")
                    if len(total_errores) > 5:
                        print(f"  ... y {len(total_errores) - 5} error(es) más")

                advertencias = sorted(
                    (
                        AdvertenciaAcumulacionSinDatos(
                            concepto_codigo=cod,
                            formato=fmt,
                            cuentas=sorted(cuentas),
                        )
                        for (cod, fmt), cuentas in advertencias_sin_datos_map.items()
                    ),
                    key=lambda a: (a.concepto_codigo, a.formato),
                )
                errores_ui = [
                    f"{e['concepto']} · atributo {e['atributo_id']} — {str(e['error'])[:80]}"
                    for e in total_errores[:20]
                ]
                if len(total_errores) > 20:
                    errores_ui.append(f"… y {len(total_errores) - 20} más (revisar consola).")

                return ResultadoAcumulacion(
                    exito=not total_errores,
                    total_inserts=total_inserts,
                    total_conceptos_solicitados=len(conceptos),
                    conceptos_omitidos_sin_elemento=sorted(set(conceptos_omitidos_sin_elemento)),
                    conceptos_sin_cuentas_en_config=sorted(set(conceptos_sin_cuentas_en_config)),
                    conceptos_sin_filas_en_hoja=sorted(set(conceptos_sin_filas_en_hoja)),
                    advertencias_sin_datos=advertencias,
                    errores_insercion=errores_ui,
                )
        except RuntimeError as e:
            if str(e) == _ACUMULAR_CANCEL_MSG:
                return ResultadoAcumulacion(
                    cancelado=True,
                    exito=False,
                    total_conceptos_solicitados=len(conceptos),
                )
            raise
        except Exception as e:
            concepto_codigo_actual = concepto.get("codigo", "N/A") if "concepto" in locals() else "N/A"
            ca = locals().get("concepto_actual", "?")
            tc = locals().get("total_conceptos", len(conceptos))
            print(f"[ERROR CRÍTICO] Concepto {concepto_codigo_actual} ({ca}/{tc}): {e}")
            import traceback

            print(traceback.format_exc())
            return ResultadoAcumulacion(
                exito=False,
                total_conceptos_solicitados=len(conceptos),
                mensaje_error_critico=str(e),
            )
