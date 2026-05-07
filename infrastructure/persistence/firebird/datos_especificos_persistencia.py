"""DATOSESPECIFICOS: catálogos dependientes, padres HIJOS y CRUD de filas usuario."""
import re
from typing import Any, Dict, List, Optional

from infrastructure.adapters.helisa_firebird import CNX_BDHelisa
from core import session
from infrastructure.adapters.proteccion_firebird import transaccion_segura

T = "DATOSESPECIFICOS"


def _intish(v: Any) -> Optional[int]:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def _conexion_empresa_ex():
    return CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")


def _parse_hijos_raw(hijos_raw: Any) -> List[int]:
    """Convierte el contenido de HIJOS a lista de códigos enteros."""
    if hijos_raw is None:
        return []
    texto = str(hijos_raw).strip()
    if not texto:
        return []
    nums = re.findall(r"\d+", texto)
    vistos = set()
    salida: List[int] = []
    for n in nums:
        v = int(n)
        if v in vistos:
            continue
        vistos.add(v)
        salida.append(v)
    return salida


def _siguiente_codigo_por_patron(codigos: List[int]) -> int:
    """Inferencia de paso entre CODIGOs existentes (frecuencia de deltas; empate por cercanía al último salto)."""
    if not codigos:
        return 1

    serie = sorted({int(c) for c in codigos if c is not None})
    if not serie:
        return 1
    if len(serie) == 1:
        unico = serie[-1]
        if unico % 100 == 0:
            return unico + 100
        if unico % 10 == 0:
            return unico + 10
        return unico + 1

    deltas: List[int] = []
    for indice in range(1, len(serie)):
        d = serie[indice] - serie[indice - 1]
        if d > 0:
            deltas.append(d)
    if not deltas:
        return serie[-1] + 1

    frecuencias: Dict[int, int] = {}
    for d in deltas:
        frecuencias[d] = frecuencias.get(d, 0) + 1

    ultimo_salto = deltas[-1]
    paso = min(
        frecuencias.keys(),
        key=lambda d: (-frecuencias[d], abs(d - ultimo_salto), d),
    )
    return serie[-1] + paso


def obtener_tabla_padre_para_catalogo_dependiente(tabla_hija: str) -> Optional[str]:
    """
    Resuelve el catálogo padre (columna TABLA) cuando `tabla_hija` depende de otro.

    Criterio: existe una fila en DATOSESPECIFICOS con HIJOS no vacío cuya lista de
    códigos intersecta los CODIGO actuales de `tabla_hija`. Esa fila pertenece al
    catálogo cuyo nombre (TABLA) es el atributo padre en UI (misma convención que
    `obtener_padres_subtipo`).
    """
    tb = str(tabla_hija or "").strip()
    if not tb:
        return None
    conn = _conexion_empresa_ex()
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT CODIGO FROM {T}
                WHERE UPPER(TRIM(TABLA)) = UPPER(TRIM(?))""",
            (tb,),
        )
        codigos_hija: set[int] = set()
        for (c,) in cur.fetchall() or []:
            n = _intish(c)
            if n is not None:
                codigos_hija.add(n)
        if not codigos_hija:
            return None
        cur.execute(
            f"""
            SELECT TABLA, HIJOS
            FROM {T}
            WHERE HIJOS IS NOT NULL
              AND TRIM(CAST(HIJOS AS VARCHAR(500))) <> ''
            ORDER BY TABLA, CODIGO
            """
        )
        mejor_tabla: Optional[str] = None
        mejor_n = 0
        for fila in cur.fetchall() or []:
            t_pad = (fila[0] or "").strip()
            if not t_pad or t_pad.upper() == tb.upper():
                continue
            hijos = set(_parse_hijos_raw(fila[1]))
            n_inter = len(hijos & codigos_hija)
            if n_inter > mejor_n:
                mejor_n = n_inter
                mejor_tabla = t_pad
        return mejor_tabla
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass


def obtener_opciones_datos_especificos(
    tabla: str,
    padre_tabla: Optional[str] = None,
    padre_valor: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Sin padre: todas las filas de `tabla`. Con padre: filas cuyo CODIGO (como texto) empieza por el código elegido en el dropdown padre."""
    if not tabla:
        return []
    conn = _conexion_empresa_ex()
    cur = None
    try:
        cur = conn.cursor()
        tb = str(tabla).strip()
        if padre_tabla is None:
            cur.execute(
                f"""SELECT CODIGO, DESCRIPCION, TIPO FROM {T}
                    WHERE UPPER(TRIM(TABLA)) = UPPER(TRIM(?)) ORDER BY CODIGO""",
                (tb,),
            )
        else:
            s = str(padre_valor or "").strip()
            if not s:
                return []
            n = _intish(padre_valor)
            pref = str(n) if n is not None else s
            cur.execute(
                f"""SELECT CODIGO, DESCRIPCION, TIPO FROM {T}
                    WHERE UPPER(TRIM(TABLA)) = UPPER(TRIM(?))
                      AND CAST(CODIGO AS VARCHAR(50)) STARTING WITH ?
                    ORDER BY CODIGO""",
                (tb, pref),
            )
        rows = cur.fetchall() or []
        return [
            {"codigo": fila[0], "descripcion": fila[1] or "", "tipo": fila[2] or 0}
            for fila in rows
        ]
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass


def obtener_padres_subtipo(tabla: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retorna padres para subtipo: registros con HIJOS no nulo/vacío.
    Incluye la lista `hijos` parseada desde la columna HIJOS.
    """
    conn = _conexion_empresa_ex()
    cur = None
    try:
        cur = conn.cursor()
        if tabla:
            cur.execute(
                f"""
                SELECT TABLA, CODIGO, DESCRIPCION, HIJOS
                FROM {T}
                WHERE UPPER(TRIM(TABLA)) = UPPER(TRIM(?))
                  AND HIJOS IS NOT NULL
                  AND TRIM(CAST(HIJOS AS VARCHAR(500))) <> ''
                ORDER BY CODIGO
                """,
                (str(tabla).strip(),),
            )
        else:
            cur.execute(
                f"""
                SELECT TABLA, CODIGO, DESCRIPCION, HIJOS
                FROM {T}
                WHERE HIJOS IS NOT NULL
                  AND TRIM(CAST(HIJOS AS VARCHAR(500))) <> ''
                ORDER BY CODIGO
                """
            )
        rows = cur.fetchall() or []
        padres: List[Dict[str, Any]] = []
        for fila in rows:
            tabla_padre = (fila[0] or "").strip()
            codigo = fila[1]
            if codigo is None:
                continue
            hijos = _parse_hijos_raw(fila[3])
            if not hijos:
                continue
            padres.append(
                {
                    "tabla": tabla_padre,
                    "codigo": int(codigo),
                    "descripcion": (fila[2] or "").strip(),
                    "hijos": hijos,
                }
            )
        return padres
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass


def obtener_opciones_datos_especificos_por_codigos(codigos: List[int]) -> List[Dict[str, Any]]:
    """Obtiene opciones por lista de CODIGO, sin filtrar por TABLA."""
    cods = [int(c) for c in codigos if c is not None]
    if not cods:
        return []
    conn = _conexion_empresa_ex()
    cur = None
    try:
        cur = conn.cursor()
        placeholders = ",".join("?" for _ in cods)
        cur.execute(
            f"""
            SELECT CODIGO, DESCRIPCION, TIPO
            FROM {T}
            WHERE CODIGO IN ({placeholders})
            ORDER BY CODIGO
            """,
            tuple(cods),
        )
        rows = cur.fetchall() or []
        return [
            {"codigo": fila[0], "descripcion": fila[1] or "", "tipo": fila[2] or 0}
            for fila in rows
        ]
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass


def actualizar_hijos_padre_subtipo(tabla: str, codigo_padre: int, hijos: List[int]) -> bool:
    """Actualiza la columna HIJOS del padre con la lista de códigos actual."""
    if not tabla or codigo_padre is None:
        return False
    hijos_limpios = [int(h) for h in hijos if h is not None]
    hijos_texto = ",".join(str(h) for h in sorted(set(hijos_limpios)))
    try:
        with transaccion_segura() as (con, cur):
            cur.execute(
                f"UPDATE {T} SET HIJOS = ? WHERE TABLA = ? AND CODIGO = ?",
                (hijos_texto, str(tabla).strip(), int(codigo_padre)),
            )
            return cur.rowcount > 0
    except Exception as e:
        print(f"Error actualizando HIJOS del padre: {e}")
        return False


def crear_dato_especifico(tabla: str, descripcion: str, codigos_base: Optional[List[int]] = None) -> Optional[int]:
    if not tabla or not (descripcion or "").strip():
        return None
    descripcion = descripcion.strip()
    try:
        with transaccion_segura() as (con, cur):
            tabla_limpia = str(tabla).strip()
            if codigos_base:
                codigos = [_intish(c) for c in codigos_base]
            else:
                cur.execute(f"SELECT CODIGO FROM {T} WHERE TABLA = ?", (tabla_limpia,))
                rows = cur.fetchall() or []
                codigos = [_intish(fila[0]) for fila in rows]
            n = _siguiente_codigo_por_patron([c for c in codigos if c is not None])

            new_id: Optional[int] = None
            try:
                cur.execute("SELECT NEXT VALUE FOR GEN_DATOSESPECIFICOS_ID FROM RDB$DATABASE")
                row = cur.fetchone()
                if row and row[0] is not None:
                    new_id = int(row[0])
            except Exception:
                cur.execute(f"SELECT COALESCE(MAX(ID), 0) + 1 FROM {T}")
                row = cur.fetchone()
                new_id = int(row[0]) if row and row[0] is not None else 1

            cur.execute(
                f"INSERT INTO {T} (ID, CODIGO, DESCRIPCION, TABLA, TIPO) VALUES (?,?,?,?,?)",
                (new_id, n, descripcion, tabla_limpia, 0),
            )
            return n
    except Exception as e:
        print(f"Error creando dato especifico: {e}")
        return None


def eliminar_dato_especifico(tabla: str, codigo: int) -> bool:
    if not tabla or codigo is None:
        return False
    try:
        with transaccion_segura() as (con, cur):
            cur.execute(
                f"DELETE FROM {T} WHERE TABLA = ? AND CODIGO = ? AND COALESCE(TIPO, 0) <= 0",
                (str(tabla).strip(), int(codigo)),
            )
            return cur.rowcount > 0
    except Exception as e:
        print(f"Error eliminando dato especifico: {e}")
        return False
