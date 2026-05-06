"""
Persistencia y utilidades SQL/cursor para HOJA_TRABAJO (agrupación, undo,
inserción de filas, deletes por concepto, cuantías/fideicomiso).

La coordinación de negocio sigue en ``FirebirdHojaTrabajoRepository`` y casos de uso.
"""
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from infrastructure.persistence.firebird.elementos_persistencia import (
    consultar_atributos,
    consultar_atributos_por_concepto,
)
from infrastructure.persistence.firebird.conceptos_persistencia import (
    consultar_conceptos_paginados,
    consultar_id_concepto,
)

# Whitelist de tablas permitidas para queries dinámicas en acumular
TABLAS_MOVIMIENTOS_PERMITIDAS = {"_trib", "_cont", ""}
TABLAS_CUENTAS_PERMITIDAS = {"cuentas_trib", "cuentas_cont"}


def agrupar_filas_hoja(
    rows: List[Tuple],
    get_id: Callable[[Tuple], Any],
    get_id_concepto: Callable[[Tuple], Any],
    get_identidad: Callable[[Tuple], Any],
) -> List[Dict[str, Any]]:
    """Agrupa filas contiguas con el mismo par (identidad, id_concepto)."""
    if not rows:
        return []
    groups: List[Dict[str, Any]] = []
    grupo_actual: Optional[Dict[str, Any]] = None
    for fila in rows:
        rid = get_id(fila)
        id_concepto = get_id_concepto(fila)
        identidad = str(get_identidad(fila) or "").strip()
        if (
            grupo_actual is None
            or grupo_actual["identidad"] != identidad
            or grupo_actual["id_concepto"] != id_concepto
        ):
            if grupo_actual is not None:
                groups.append(grupo_actual)
            grupo_actual = {
                "identidad": identidad,
                "id_concepto": id_concepto,
                "primer_id": rid,
                "rows": [fila],
            }
        else:
            grupo_actual["rows"].append(fila)
    if grupo_actual is not None:
        groups.append(grupo_actual)

    for grupo in groups:
        grupo["group_key"] = f"{grupo['id_concepto']}|{grupo['identidad']}"
    return groups


# Fideicomiso masivo (atributos por descripción; lote IN < límite Firebird ~1500)
_FIDEI_DESC_TIPO = "TIPO DE FIDEICOMISO"
_FIDEI_DESC_SUBTIPO = "SUBTIPO DE FIDEICOMISO"
_FIDEI_BATCH_IN = 450


def tupla_ids_tdoc_atributo() -> Tuple[Tuple[Any, ...], str]:
    """
    IDs de atributos con filtro 'tdoc' y cadena para IN (...) en SQL dinámico.
    Si hay un solo ID en BD se duplica con -1 (misma convención que el código previo).
    """
    atrs_tdoc = consultar_atributos(filtro="tdoc")
    ids_tdoc = tuple(atr[0] for atr in atrs_tdoc)
    if len(ids_tdoc) == 1:
        ids_tdoc = ids_tdoc + (-1,)
    ids_tdoc_str = ",".join(
        str(id_val) for id_val in ids_tdoc if isinstance(id_val, (int, str)) and str(id_val).isdigit()
    )
    return ids_tdoc, ids_tdoc_str


def _ids_atributos_fideicomiso(concepto: Dict[str, str]) -> Tuple[Optional[int], Optional[int]]:
    """IDs de atributos tipo/subtipo de fideicomiso para el concepto."""
    id_t, id_s = None, None
    for a in consultar_atributos_por_concepto(concepto):
        if len(a) < 3:
            continue
        d = str(a[2] or "").strip().upper()
        if d == _FIDEI_DESC_TIPO:
            id_t = int(a[0])
        elif d == _FIDEI_DESC_SUBTIPO:
            id_s = int(a[0])
    return id_t, id_s


def _distinct_valores_hoja_atributo(cur, id_concepto: int, id_atr: int) -> List[str]:
    cur.execute(
        """
        SELECT DISTINCT TRIM(VALOR)
        FROM HOJA_TRABAJO
        WHERE IDCONCEPTO = ? AND IDATRIBUTO = ? AND TRIM(VALOR) <> ''
        """,
        (id_concepto, id_atr),
    )
    return sorted(
        {str(fila[0]).strip() for fila in cur.fetchall() if fila and fila[0] is not None}
    )


def _identidades_con_valor_atributo(cur, id_concepto: int, id_atr: int, valor: str) -> set:
    cur.execute(
        """
        SELECT DISTINCT IDENTIDADTERCERO
        FROM HOJA_TRABAJO
        WHERE IDCONCEPTO = ? AND IDATRIBUTO = ? AND TRIM(VALOR) = TRIM(?)
        """,
        (id_concepto, id_atr, valor),
    )
    return {fila[0] for fila in cur.fetchall() if fila and fila[0] is not None}


def _update_hoja_valor_por_identidades(
    cur, valor: str, id_concepto: int, id_atr: int, identidades: List
) -> None:
    for inicio in range(0, len(identidades), _FIDEI_BATCH_IN):
        chunk = identidades[inicio : inicio + _FIDEI_BATCH_IN]
        marks = ",".join("?" for _ in chunk)
        cur.execute(
            f"""
            UPDATE HOJA_TRABAJO
            SET VALOR = ?
            WHERE IDCONCEPTO = ? AND IDATRIBUTO = ?
              AND IDENTIDADTERCERO IN ({marks})
            """,
            tuple([valor, id_concepto, id_atr] + chunk),
        )


def _parsear_clave(clave: str) -> Tuple[int, str]:
    """Convierte clave 'id_concepto|identidad' en (id_concepto, identidad)."""
    if "|" in clave:
        id_c, ident = clave.split("|", 1)
        return (int(id_c.strip()), ident.strip())
    return (0, clave.strip())


def _to_float(v: Any) -> float:
    """Parsea valor a float. Vacío o None -> 0.0."""
    try:
        return float(str(v).replace(",", "")) if v not in (None, "") else 0.0
    except Exception:
        return 0.0


def _obtener_codigo_y_formato_concepto(concepto: Union[Dict[str, str], str]) -> Optional[Tuple[str, str]]:
    """
    Normaliza un concepto a (codigo, formato).
    Retorna None si el input no cumple con la estructura esperada.
    """
    if not isinstance(concepto, dict):
        return None
    codigo = str(concepto.get("codigo", "")).strip()
    formato = str(concepto.get("formato", "")).strip()
    if not codigo or not formato:
        return None
    return codigo, formato


def _resolver_id_y_config_concepto(
    concepto: Union[Dict[str, str], str],
    *,
    mensaje_error_invalid: str,
    mensaje_error_not_found: str,
) -> Tuple[Optional[int], Optional[Dict[str, Any]], Optional[str]]:
    """Devuelve (id_concepto, fila_dict_config, mensaje_error|None)."""
    codigo_formato = _obtener_codigo_y_formato_concepto(concepto)
    if not codigo_formato:
        return None, None, mensaje_error_invalid

    codigo, formato = codigo_formato
    id_concepto = consultar_id_concepto(codigo, formato)
    if id_concepto is None:
        return None, None, f"{mensaje_error_not_found}: {codigo} - {formato}"

    conceptos, _total = consultar_conceptos_paginados(
        offset=0, limit=1000, filtro=codigo
    )
    concepto_encontrado = next(
        (c for c in conceptos if c.get("codigo") == codigo and c.get("formato") == formato),
        None,
    )
    if not concepto_encontrado:
        return None, None, "Concepto no encontrado en BD."

    return id_concepto, concepto_encontrado, None


def _obtener_primer_valor_por_registro(cur, id_concepto: int) -> Dict[str, Tuple[int, Any]]:
    """Por identidad: primera fila (menor HOJA_TRABAJO.ID) con atributo CLASE=1."""
    cur.execute(
        """
        SELECT ht.ID, TRIM(ht.IDENTIDADTERCERO), ht.VALOR
        FROM HOJA_TRABAJO ht
        INNER JOIN ATRIBUTOS a ON a.ID = ht.IDATRIBUTO
        WHERE ht.IDCONCEPTO = ? AND a.CLASE = 1
        ORDER BY TRIM(ht.IDENTIDADTERCERO), ht.ID
        """,
        (id_concepto,),
    )
    rows = cur.fetchall()
    resultado: Dict[str, Tuple[int, Any]] = {}
    for hoja_id, ident, valor in rows:
        ident = str(ident or "").strip()
        if ident and ident not in resultado:
            resultado[ident] = (hoja_id, valor)
    return resultado


# --- Inserciones y UNDO reutilizadas en varias operaciones de hoja ---


def insert_fila_hoja_trabajo(
    cur,
    id_concepto: int,
    id_atributo: int,
    idelemento: int,
    valor: Any,
    identidad_tercero: Any,
) -> None:
    """Inserta una fila estándar en HOJA_TRABAJO (misma forma en CRUD, acumulación y deshacer)."""
    cur.execute(
        """
        INSERT INTO HOJA_TRABAJO (Idconcepto, Idatributo, Idelemento, Valor, Identidadtercero)
        VALUES (?, ?, ?, ?, ?)
        """,
        (id_concepto, id_atributo, idelemento, valor, identidad_tercero),
    )


def insert_undo_hoja_trabajo(cur, tipo_op: int, id_concepto: int, payload: str, fecha) -> None:
    """Registra un snapshot en HOJA_TRABAJO_UNDO."""
    cur.execute(
        "INSERT INTO HOJA_TRABAJO_UNDO (TipoOp, IdConcepto, Payload, CreatedAt) VALUES (?, ?, ?, ?)",
        (tipo_op, id_concepto, payload, fecha),
    )


def fetch_undo_registros_por_tipo(cur, tipo_op: int, id_concepto: int):
    """Lista registros UNDO para un concepto y tipo de operación (orden reciente primero)."""
    cur.execute(
        "SELECT Id, Payload FROM HOJA_TRABAJO_UNDO WHERE TipoOp = ? AND IdConcepto = ? ORDER BY Id DESC",
        (tipo_op, id_concepto),
    )
    return cur.fetchall()


def delete_undo_por_id(cur, undo_id: int) -> None:
    cur.execute("DELETE FROM HOJA_TRABAJO_UNDO WHERE Id = ?", (undo_id,))


def obtener_id_concepto_y_elemento(cur, id_concepto: int) -> Optional[Tuple[int, int]]:
    """Par (id_concepto, id_elemento) desde CONCEPTOS + ELEMENTOS."""
    cur.execute(
        "SELECT c.ID, e.ID FROM CONCEPTOS c INNER JOIN ELEMENTOS e ON e.idconcepto = c.ID WHERE c.ID = ?",
        (id_concepto,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return int(row[0]), int(row[1])


def mapear_atributos_agrupar_cuantias(attrs: list) -> Dict[str, Any]:
    """
    Para agrupar cuantías: atributos CLASE=1 sumables e IDs por descripción
    (razón social, Nº identificación, dirección, tipo documento).
    """
    sumables = {a[0] for a in attrs if len(a) >= 4 and str(a[3]) == "1"}
    id_atr_razon = id_atr_identidad = id_atr_direccion = id_atr_tipo_documento = None
    for a in attrs:
        desc = (a[2] or "").upper() if len(a) > 2 else ""
        if "RAZÓN SOCIAL" in desc or "RAZON SOCIAL" in desc:
            id_atr_razon = a[0]
        elif "NÚMERO DE IDENTIFICACIÓN" in desc or "NUMERO DE IDENTIFICACION" in desc:
            id_atr_identidad = a[0]
        elif "DIRECCIÓN" in desc or "DIRECCION" in desc:
            id_atr_direccion = a[0]
        elif "TIPO" in desc and "DOCUMENTO" in desc:
            id_atr_tipo_documento = a[0]
    return {
        "sumables": sumables,
        "id_atr_razon": id_atr_razon,
        "id_atr_identidad": id_atr_identidad,
        "id_atr_direccion": id_atr_direccion,
        "id_atr_tipo_documento": id_atr_tipo_documento,
    }


def resolver_id_concepto_legacy(concepto: Union[Dict[str, str], str]) -> Optional[int]:
    """ID de concepto: dict con codigo/formato o código legado vía listado paginado."""
    if isinstance(concepto, dict) and "codigo" in concepto and "formato" in concepto:
        return consultar_id_concepto(concepto["codigo"], concepto["formato"])
    conceptos_compat, _ = consultar_conceptos_paginados(
        offset=0, limit=1, filtro=concepto
    )
    if not conceptos_compat:
        return None
    return conceptos_compat[0]["id"]


def delete_hoja_trabajo_por_id_concepto_cursor(
    cur: Any,
    id_concepto: int,
    filtro: Optional[float] = None,
    campo_id: Optional[int] = None,
) -> None:
    """DELETE por concepto; con filtro+campo_id solo filas con cuantía bajo umbral."""
    if filtro is None or campo_id is None:
        cur.execute(
            "DELETE FROM HOJA_TRABAJO WHERE IDCONCEPTO = ?",
            (id_concepto,),
        )
        return
    cur.execute(
        """
        DELETE FROM HOJA_TRABAJO
        WHERE IDENTIDADTERCERO IN (
            SELECT DISTINCT IDENTIDADTERCERO
            FROM HOJA_TRABAJO
            WHERE IDCONCEPTO = ?
              AND IDATRIBUTO = ?
              AND CAST(VALOR AS DECIMAL(18, 2)) < ?
        )
        AND IDCONCEPTO = ?
        """,
        (id_concepto, campo_id, filtro, id_concepto),
    )
