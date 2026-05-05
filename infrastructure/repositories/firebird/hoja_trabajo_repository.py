"""Repositorio Firebird para el módulo Hoja de Trabajo (consultas y mutaciones)."""

import json
from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Optional, Tuple, Union
from application.ports.hoja_trabajo_ports import (
    ConceptoLegacyMap,
    ConceptoRef,
    EntradaHojaPayload,
    ResultadoHojaPaginada,
)
from domain.entities.concepto_hoja_trabajo import ConceptoHojaTrabajo

from infrastructure.adapters.helisa_firebird import CNX_BDHelisa
from infrastructure.adapters.proteccion_firebird import transaccion_segura
from infrastructure.persistence.firebird.conceptos_persistencia import (
    consultar_conceptos_paginados,
    consultar_id_concepto,
)
from infrastructure.persistence.firebird.elementos_persistencia import consultar_atributos_por_concepto
from infrastructure.persistence.firebird.empresas_persistencia import obtener_info_empresa
from infrastructure.persistence.firebird.hoja_trabajo_persistencia import (
    _distinct_valores_hoja_atributo,
    _identidades_con_valor_atributo,
    _ids_atributos_fideicomiso,
    _obtener_primer_valor_por_registro,
    _parsear_clave,
    _resolver_id_y_config_concepto,
    _to_float,
    _update_hoja_valor_por_identidades,
    agrupar_filas_hoja,
    delete_hoja_trabajo_por_id_concepto_cursor,
    delete_undo_por_id,
    fetch_undo_registros_por_tipo,
    insert_fila_hoja_trabajo,
    insert_undo_hoja_trabajo,
    mapear_atributos_agrupar_cuantias,
    obtener_id_concepto_y_elemento,
    resolver_id_concepto_legacy,
    tupla_ids_tdoc_atributo,
)
from core import session


def _payload_undo_desde_blob(payload_blob: Any) -> dict:
    """Decodifica JSON almacenado en BLOB o string del registro UNDO."""
    payload_str = payload_blob.read() if hasattr(payload_blob, "read") else str(payload_blob or "{}")
    return json.loads(payload_str)


def _ids_csv(ids: List[Any]) -> str:
    """Convierte lista de IDs a CSV para cláusulas IN; retorna '0' cuando viene vacía."""
    return ",".join(str(x) for x in ids) if ids else "0"


def _restar_monto_en_atributo_base(
    cur: Any,
    *,
    id_concepto: int,
    attr_id: int,
    identidad: str,
    monto: Any,
) -> None:
    """Resta un monto sobre un atributo base de la identidad si existe fila actual."""
    cur.execute(
        "SELECT VALOR FROM HOJA_TRABAJO WHERE IDCONCEPTO = ? AND IDATRIBUTO = ? AND TRIM(IDENTIDADTERCERO) = TRIM(?)",
        (id_concepto, attr_id, identidad),
    )
    r = cur.fetchone()
    if not r:
        return
    base = _to_float(r[0])
    nuevo = base - _to_float(monto)
    cur.execute(
        "UPDATE HOJA_TRABAJO SET VALOR = ? WHERE IDCONCEPTO = ? AND IDATRIBUTO = ? AND TRIM(IDENTIDADTERCERO) = TRIM(?)",
        (str(nuevo) if nuevo != 0 else "0", id_concepto, attr_id, identidad),
    )


def _restar_sumas_por_atributo(
    cur: Any,
    *,
    id_concepto: int,
    identidad_base: str,
    sumas_por_attr: Dict[Any, Any],
) -> None:
    """Aplica resta por atributo para un payload de undo ignorando claves no numéricas."""
    for attr_id_str, monto in sumas_por_attr.items():
        try:
            attr_id = int(attr_id_str)
        except (ValueError, TypeError):
            continue
        _restar_monto_en_atributo_base(
            cur,
            id_concepto=id_concepto,
            attr_id=attr_id,
            identidad=identidad_base,
            monto=monto,
        )


def _where_concepto_filtro_hoja(
    legacy_concepto: Optional[Any],
    filtro: Optional[str],
) -> Tuple[str, List[Any]]:
    """Arma WHERE y parámetros compartidos por el conteo, la paginación de claves y el detalle de filas."""
    conds_rows: List[str] = []
    params: List[Any] = []

    if legacy_concepto:
        if isinstance(legacy_concepto, dict) and "codigo" in legacy_concepto and "formato" in legacy_concepto:
            id_concepto = consultar_id_concepto(
                legacy_concepto["codigo"], legacy_concepto["formato"]
            )
            if id_concepto:
                conds_rows.append("c.ID = ?")
                params.append(id_concepto)
        elif isinstance(legacy_concepto, (int, str)) and str(legacy_concepto).isdigit():
            conds_rows.append("c.ID = ?")
            params.append(int(legacy_concepto))
        else:
            conds_rows.append("c.CODIGO = ?")
            params.append(str(legacy_concepto))

    if filtro:
        conds_rows.append("UPPER(ht.IDENTIDADTERCERO) LIKE UPPER(?)")
        params.append(f"%{filtro}%")

    where_clause = "WHERE " + " AND ".join(conds_rows) if conds_rows else ""
    return where_clause, params


def _solo_conceptos_desde_hoja(cur: Any) -> List[ConceptoLegacyMap]:
    """Lista códigos/formatos distintos que tienen filas en HOJA_TRABAJO."""
    cur.execute(
        """
        SELECT c.CODIGO, f.FORMATO
        FROM (
            SELECT DISTINCT IDCONCEPTO FROM HOJA_TRABAJO
        ) ht
        INNER JOIN CONCEPTOS c ON c.ID = ht.IDCONCEPTO
        INNER JOIN FORMATOS f ON f.ID = c.IDFORMATO
        ORDER BY c.CODIGO, f.FORMATO
        """
    )
    rows = cur.fetchall()
    return [{"codigo": r[0], "formato": r[1]} for r in rows]


def _registros_ui_desde_grupos_hoja(groups: List[Any]) -> Dict[str, dict]:
    """Convierte grupos de `agrupar_filas_hoja` al dict expuesto a la UI por identidad/concepto."""
    resultado: Dict[str, dict] = {}
    for grupo in groups:
        clave = grupo["group_key"]
        identidad = grupo["identidad"]
        registro_agrupado: Dict[str, Any] = {}
        for r in grupo["rows"]:
            descripcion = r[5]
            valor = r[7]
            if descripcion != "Número de Identificación":
                registro_agrupado[descripcion] = valor or ""
        registro_agrupado["FORMATO"] = grupo["rows"][0][6]
        registro_agrupado["Concepto"] = grupo["rows"][0][4]
        registro_agrupado["Número de Identificación"] = identidad
        registro_agrupado["id_concepto"] = grupo["id_concepto"]
        resultado[clave] = registro_agrupado
    return resultado


def _consultar_hoja_paginada_en_cursor(
    cur: Any,
    *,
    offset: int,
    limit: int,
    legacy_concepto: Optional[Any],
    filtro: Optional[str],
) -> ResultadoHojaPaginada:
    """Consulta paginada de la hoja: total, página de claves, detalle y mapa para la grilla."""
    where_clause, params = _where_concepto_filtro_hoja(legacy_concepto, filtro)

    sql_total = (
        """
        SELECT COUNT(*)
        FROM (
            SELECT DISTINCT
                TRIM(ht.IDENTIDADTERCERO) AS IDENTIDADTERCERO,
                ht.IDCONCEPTO
            FROM HOJA_TRABAJO ht
            INNER JOIN CONCEPTOS c ON c.ID = ht.IDCONCEPTO
        """
        + where_clause
        + """
        ) x
        """
    )
    cur.execute(sql_total, tuple(params))
    row_total = cur.fetchone()
    total_identidades = int(row_total[0]) if row_total and row_total[0] is not None else 0

    sql_keys = (
        """
        SELECT FIRST ? SKIP ?
            ht.IDENTIDADTERCERO,
            ht.IDCONCEPTO
        FROM HOJA_TRABAJO ht
        INNER JOIN CONCEPTOS c ON c.ID = ht.IDCONCEPTO
        """
        + where_clause
        + """
        GROUP BY ht.IDENTIDADTERCERO, ht.IDCONCEPTO
        ORDER BY ht.IDENTIDADTERCERO, ht.IDCONCEPTO
        """
    )
    cur.execute(sql_keys, tuple([limit, offset] + params))
    pares_pagina = cur.fetchall()
    if not pares_pagina:
        return ({}, False, total_identidades)

    cur.execute(sql_keys, tuple([1, offset + limit] + params))
    has_more = cur.fetchone() is not None

    cond_pares = " OR ".join(
        ["(TRIM(ht.IDENTIDADTERCERO) = ? AND ht.IDCONCEPTO = ?)"] * len(pares_pagina)
    )
    params_rows = list(params)
    for ident, id_c in pares_pagina:
        params_rows.append(str(ident).strip() if ident else "")
        params_rows.append(id_c)
    sql_rows = (
        """
        SELECT
            ht.ID,
            ht.IDCONCEPTO,
            ht.IDATRIBUTO,
            ht.IDELEMENTO,
            c.CODIGO AS CODIGO,
            a.DESCRIPCION,
            f.FORMATO,
            ht.VALOR,
            ht.IDENTIDADTERCERO
        FROM HOJA_TRABAJO ht
        INNER JOIN ELEMENTOS e ON e.ID = ht.IDELEMENTO
        INNER JOIN ATRIBUTOS a ON a.ID = ht.IDATRIBUTO
        INNER JOIN FORMATOS f ON f.ID = e.IDFORMATO
        INNER JOIN CONCEPTOS c ON c.ID = ht.IDCONCEPTO
        """
        + where_clause
        + """
        AND ("""
        + cond_pares
        + """)
        ORDER BY ht.IDENTIDADTERCERO, ht.IDCONCEPTO, ht.ID
        """
    )
    cur.execute(sql_rows, tuple(params_rows))
    rows = cur.fetchall()
    groups = agrupar_filas_hoja(
        rows,
        get_id=lambda r: r[0],
        get_id_concepto=lambda r: r[1],
        get_identidad=lambda r: r[8],
    )
    resultado = _registros_ui_desde_grupos_hoja(groups)
    return (resultado, has_more, total_identidades)


def _resolver_concepto_y_elemento_entrada(
    cur: Any,
    codigo_concepto: str,
    formato_concepto: str,
) -> Optional[Tuple[int, int]]:
    """
    Obtiene (id_concepto, id_elemento) según si el payload trae formato o solo código.
    Retorna None si no existe fila.
    """
    if formato_concepto:
        id_concepto = consultar_id_concepto(codigo_concepto, formato_concepto)
        if id_concepto is None:
            return None
        cur.execute(
            """
            SELECT c.ID, e.ID
            FROM CONCEPTOS c
            INNER JOIN ELEMENTOS e ON e.idconcepto = c.ID
            WHERE c.ID = ?
            """,
            (id_concepto,),
        )
    else:
        cur.execute(
            """
            SELECT c.ID, e.ID
            FROM CONCEPTOS c
            INNER JOIN ELEMENTOS e ON e.idconcepto = c.ID
            WHERE c.codigo = ?
            """,
            (codigo_concepto,),
        )
    row = cur.fetchone()
    if not row:
        return None
    return int(row[0]), int(row[1])


def _actualizar_valor_entrada_por_descripcion(
    cur: Any,
    *,
    valor: Any,
    id_concepto: int,
    identidad: str,
    codigo_concepto: str,
    formato_concepto: str,
    descripcion: str,
) -> None:
    """Actualiza `HOJA_TRABAJO.VALOR` resolviendo `IDATRIBUTO` por descripción y concepto."""
    if formato_concepto:
        cur.execute(
            """
            UPDATE HOJA_TRABAJO ht
            SET ht.VALOR = ?
            WHERE ht.IDCONCEPTO = ? AND TRIM(ht.IDENTIDADTERCERO) = TRIM(?)
            AND ht.IDATRIBUTO = (
                SELECT a.ID
                FROM CONCEPTOS c
                INNER JOIN FORMATOS f ON f.ID = c.IDFORMATO
                JOIN ELEMENTOS e ON e.IDCONCEPTO = c.ID
                JOIN ATRIBUTOS a ON a.IDELEMENTO = e.ID
                WHERE c.CODIGO = ? AND f.FORMATO = ?
                AND a.DESCRIPCION = ?
            )
            """,
            (
                valor or "",
                id_concepto,
                identidad,
                codigo_concepto,
                formato_concepto,
                descripcion,
            ),
        )
        return
    cur.execute(
        """
        UPDATE HOJA_TRABAJO ht
        SET ht.VALOR = ?
        WHERE ht.IDCONCEPTO = ? AND TRIM(ht.IDENTIDADTERCERO) = TRIM(?)
        AND ht.IDATRIBUTO = (
            SELECT a.ID
            FROM CONCEPTOS c
            JOIN ELEMENTOS e ON e.IDCONCEPTO = c.ID
            JOIN ATRIBUTOS a ON a.IDELEMENTO = e.ID
            WHERE c.CODIGO = ?
            AND a.DESCRIPCION = ?
        )
        """,
        (
            valor or "",
            id_concepto,
            identidad,
            codigo_concepto,
            descripcion,
        ),
    )


class FirebirdHojaTrabajoRepository:
    """Implementación Firebird del puerto de hoja de trabajo."""

    @staticmethod
    def _legacy_concepto(concepto: Union[ConceptoRef, int, None]) -> Union[Dict[str, str], int, str, None]:
        """
        Convierte entidades de dominio al payload esperado por la persistencia de hoja.

        Se mantiene dict/string/int para compatibilidad con funciones históricas.
        """
        if isinstance(concepto, ConceptoHojaTrabajo):
            return concepto.as_dict()
        return concepto

    def obtener_hoja_trabajo(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        concepto: Optional[Union[ConceptoRef, int]] = None,
        filtro: Optional[str] = None,
        solo_conceptos: bool = False,
    ) -> Union[List[ConceptoLegacyMap], ResultadoHojaPaginada]:
        if offset < 0 or limit < 0:
            raise ValueError("offset y limit deben ser valores no negativos")
        legacy_concepto = self._legacy_concepto(concepto)
        conn = None
        cur = None
        try:
            conn = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
            cur = conn.cursor()

            if solo_conceptos:
                return _solo_conceptos_desde_hoja(cur)

            return _consultar_hoja_paginada_en_cursor(
                cur,
                offset=offset,
                limit=limit,
                legacy_concepto=legacy_concepto,
                filtro=filtro,
            )
        except Exception:
            return ({}, False, 0) if not solo_conceptos else []
        finally:
            if cur is not None:
                try:
                    cur.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def obtener_conceptos(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        filtro: Optional[str] = None,
    ) -> Tuple[List[ConceptoLegacyMap], int]:
        return consultar_conceptos_paginados(
            offset=offset,
            limit=limit,
            filtro=filtro,
        )

    def eliminar_grupo_filas_hoja(
        self, id_concepto: int, identidad: str
    ) -> Union[bool, Exception]:
        try:
            with transaccion_segura() as (_con, cur):
                cur.execute(
                    """
                    DELETE FROM HOJA_TRABAJO
                    WHERE IDCONCEPTO = ? AND TRIM(IDENTIDADTERCERO) = TRIM(?)
                    """,
                    (id_concepto, identidad),
                )
            return True
        except Exception as e:
            return e

    def unificar_grupos_hoja_trabajo(
        self,
        concepto: ConceptoRef,
        claves: List[str],
    ) -> Union[bool, str, Exception]:
        if not claves or len(claves) < 2:
            return "Debe seleccionar al menos dos filas para unificar."

        try:
            id_concepto, base_id = _parsear_clave(claves[0])
            if not id_concepto or not base_id:
                return "Clave de destino inválida."

            identidades: List[str] = []
            for c in claves:
                id_c, ident = _parsear_clave(c)
                if id_c != id_concepto:
                    return "Todas las filas deben ser del mismo concepto."
                identidades.append(ident)

            base_id = identidades[0]
            resto = [i for i in identidades[1:] if i and i != base_id]
            if not resto:
                return "Debe seleccionar al menos una fila distinta a la destino para unificar."

            with transaccion_segura() as (_con, cur):
                attrs = consultar_atributos_por_concepto(id_concepto)
                sumables = {a[0] for a in attrs if len(a) >= 4 and str(a[3]) == "1"}

                placeholders = ",".join(["?"] * len(identidades))
                cur.execute(
                    f"""
                    SELECT IDATRIBUTO, TRIM(IDENTIDADTERCERO), VALOR
                    FROM HOJA_TRABAJO
                    WHERE IDCONCEPTO = ?
                      AND TRIM(IDENTIDADTERCERO) IN ({placeholders})
                    """,
                    [id_concepto, *[str(i).strip() for i in identidades]],
                )
                rows = cur.fetchall()

                valores: Dict[str, Dict[int, object]] = {}
                for attr_id, identidad, valor in rows:
                    identidad = str(identidad or "").strip()
                    if identidad not in valores:
                        valores[identidad] = {}
                    valores[identidad][attr_id] = valor

                sumas_por_attr: Dict[int, float] = {}
                for attr_id in sumables:
                    base_val = _to_float(valores.get(base_id, {}).get(attr_id))
                    suma = 0.0
                    for ident in resto:
                        suma += _to_float(valores.get(ident, {}).get(attr_id))
                    if suma != 0:
                        sumas_por_attr[attr_id] = suma
                    nuevo = base_val + suma
                    cur.execute(
                        """
                        UPDATE HOJA_TRABAJO
                        SET VALOR = ?
                        WHERE IDCONCEPTO = ? AND IDATRIBUTO = ? AND TRIM(IDENTIDADTERCERO) = TRIM(?)
                        """,
                        (str(nuevo), id_concepto, attr_id, base_id),
                    )

                filas_restaurar = []
                if resto:
                    placeholders_resto = ",".join(["?"] * len(resto))
                    cur.execute(
                        f"""
                        SELECT IDCONCEPTO, IDATRIBUTO, IDELEMENTO, VALOR, IDENTIDADTERCERO
                        FROM HOJA_TRABAJO
                        WHERE IDCONCEPTO = ?
                          AND TRIM(IDENTIDADTERCERO) IN ({placeholders_resto})
                        """,
                        [id_concepto, *[str(i).strip() for i in resto]],
                    )
                    for row in cur.fetchall():
                        ident_raw = str(row[4] or "")
                        filas_restaurar.append(
                            {
                                "idc": row[0],
                                "ida": row[1],
                                "ide": row[2],
                                "val": row[3] or "",
                                "ident": ident_raw.strip(),
                                "ident_raw": ident_raw,
                            }
                        )

                    idelemento = filas_restaurar[0]["ide"] if filas_restaurar else None
                    payload = json.dumps(
                        {
                            "base_id": base_id,
                            "sumas": {str(k): v for k, v in sumas_por_attr.items()},
                            "filas_restaurar": filas_restaurar,
                            "idelemento": idelemento,
                        },
                        ensure_ascii=False,
                    )
                    insert_undo_hoja_trabajo(cur, 2, id_concepto, payload, date.today())

                if resto:
                    placeholders_resto = ",".join(["?"] * len(resto))
                    cur.execute(
                        f"""
                        DELETE FROM HOJA_TRABAJO
                        WHERE IDCONCEPTO = ?
                          AND TRIM(IDENTIDADTERCERO) IN ({placeholders_resto})
                        """,
                        [id_concepto, *[str(i).strip() for i in resto]],
                    )

            return True
        except Exception as e:
            return e

    def obtener_identidades_a_agrupar_cuantias(
        self, concepto: ConceptoRef
    ) -> List[str]:
        legacy_concepto = self._legacy_concepto(concepto)
        try:
            id_concepto, concepto_encontrado, _error = _resolver_id_y_config_concepto(
                legacy_concepto,
                mensaje_error_invalid="Concepto inválido",
                mensaje_error_not_found="Concepto no encontrado",
            )
            if not id_concepto or not concepto_encontrado:
                return []
            cc_valor_str = str(concepto_encontrado.get("cc_mm_valor", "")).strip()
            if not cc_valor_str:
                return []
            cc_valor_float = _to_float(cc_valor_str)
            conn = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
            cur = conn.cursor()
            try:
                primer_por_ident = _obtener_primer_valor_por_registro(cur, id_concepto)
            finally:
                cur.close()
                conn.close()
            return [
                ident
                for ident, (_, val) in primer_por_ident.items()
                if _to_float(val) < cc_valor_float and not ident.strip().endswith("|ex")
            ]
        except Exception:
            return []

    def agrupar_cuantias_menores(
        self, concepto: ConceptoRef
    ) -> Union[bool, str]:
        legacy_concepto = self._legacy_concepto(concepto)
        try:
            with transaccion_segura() as (_con, cur):
                id_concepto, concepto_encontrado, error_concepto = _resolver_id_y_config_concepto(
                    legacy_concepto,
                    mensaje_error_invalid="Concepto debe ser un diccionario con 'codigo' y 'formato'",
                    mensaje_error_not_found="Concepto no encontrado",
                )
                if error_concepto:
                    return error_concepto
                if not id_concepto or not concepto_encontrado:
                    return "No se pudo resolver el concepto."
                cc_identidad_base = str(concepto_encontrado.get("cc_mm_identidad", "")).strip()
                cc_identidad = f"{cc_identidad_base}|ex"
                cc_nombre = str(concepto_encontrado.get("cc_mm_nombre", "")).strip()
                cc_valor_str = str(concepto_encontrado.get("cc_mm_valor", "")).strip()
                if not cc_identidad or not cc_nombre or not cc_valor_str:
                    return "El concepto no tiene cc_mm_identidad, cc_mm_nombre y cc_mm_valor configurados."
                cc_valor_float = _to_float(cc_valor_str)

                attrs = consultar_atributos_por_concepto(legacy_concepto)
                data_mapa = mapear_atributos_agrupar_cuantias(attrs)
                sumables = data_mapa["sumables"]
                id_atr_razon = data_mapa["id_atr_razon"]
                id_atr_identidad = data_mapa["id_atr_identidad"]
                id_atr_direccion = data_mapa["id_atr_direccion"]
                id_atr_tipo_documento = data_mapa["id_atr_tipo_documento"]

                direccion_empresa = str((session.EMPRESA_ACTUAL or {}).get("direccion", "") or "").strip()
                if not direccion_empresa:
                    producto = (session.EMPRESA_ACTUAL or {}).get("producto")
                    codigo_empresa = (session.EMPRESA_ACTUAL or {}).get("codigo")
                    if producto and codigo_empresa is not None:
                        info_empresa = obtener_info_empresa(producto, codigo_empresa)
                        if isinstance(info_empresa, dict):
                            direccion_empresa = str(info_empresa.get("direccion", "") or "").strip()

                par_ce = obtener_id_concepto_y_elemento(cur, id_concepto)
                if not par_ce:
                    return "Elemento no encontrado para el concepto."
                _, idelemento = par_ce

                primer_por_ident = _obtener_primer_valor_por_registro(cur, id_concepto)
                identidades_agrupar = [
                    ident
                    for ident, (_, val) in primer_por_ident.items()
                    if _to_float(val) < cc_valor_float and not ident.strip().endswith("|ex")
                ]
                if not identidades_agrupar:
                    return "No hay registros con cuantía menor al umbral configurado."

                placeholders = ",".join(["?"] * len(identidades_agrupar))
                cur.execute(
                    f"""
                    SELECT ht.IDATRIBUTO, TRIM(ht.IDENTIDADTERCERO), ht.VALOR
                    FROM HOJA_TRABAJO ht
                    INNER JOIN ATRIBUTOS a ON a.ID = ht.IDATRIBUTO
                    WHERE ht.IDCONCEPTO = ? AND TRIM(ht.IDENTIDADTERCERO) IN ({placeholders})
                    """,
                    [id_concepto, *[str(i).strip() for i in identidades_agrupar]],
                )
                rows = cur.fetchall()
                suma_por_attr: Dict[int, float] = defaultdict(float)
                for attr_id, ident, valor in rows:
                    ident = str(ident or "").strip()
                    if ident in identidades_agrupar and attr_id in sumables:
                        suma_por_attr[attr_id] += _to_float(valor)

                identidades_a_eliminar = [i for i in identidades_agrupar if str(i).strip() != cc_identidad.strip()]
                filas_restaurar = []
                if identidades_a_eliminar:
                    ph = ",".join(["?"] * len(identidades_a_eliminar))
                    cur.execute(
                        f"""
                        SELECT Id, IDCONCEPTO, IDATRIBUTO, IDELEMENTO, VALOR, TRIM(IDENTIDADTERCERO)
                        FROM HOJA_TRABAJO
                        WHERE IDCONCEPTO = ? AND TRIM(IDENTIDADTERCERO) IN ({ph})
                        """,
                        [id_concepto, *[str(i).strip() for i in identidades_a_eliminar]],
                    )
                    for row in cur.fetchall():
                        filas_restaurar.append(
                            {
                                "id": row[0],
                                "idc": row[1],
                                "ida": row[2],
                                "ide": row[3],
                                "val": row[4] or "",
                                "ident": str(row[5] or "").strip(),
                            }
                        )

                payload = json.dumps(
                    {
                        "filas_restaurar": filas_restaurar,
                        "cc_identidad": cc_identidad,
                        "cc_existia": False,
                        "suma_restar": {},
                        "idelemento": idelemento,
                    },
                    ensure_ascii=False,
                )
                cur.execute(
                    "SELECT 1 FROM HOJA_TRABAJO WHERE IDCONCEPTO = ? AND TRIM(IDENTIDADTERCERO) = TRIM(?)",
                    (id_concepto, cc_identidad),
                )
                cc_existia = cur.fetchone() is not None
                if cc_existia:
                    pl = json.loads(payload)
                    pl["cc_existia"] = True
                    pl["suma_restar"] = {str(k): v for k, v in suma_por_attr.items()}
                    payload = json.dumps(pl, ensure_ascii=False)
                insert_undo_hoja_trabajo(cur, 0, id_concepto, payload, date.today())

                cc_identidad_padded = cc_identidad.ljust(20)
                if cc_existia:
                    for attr_id, total in suma_por_attr.items():
                        cur.execute(
                            """
                            SELECT VALOR FROM HOJA_TRABAJO
                            WHERE IDCONCEPTO = ? AND IDATRIBUTO = ? AND TRIM(IDENTIDADTERCERO) = TRIM(?)
                            """,
                            (id_concepto, attr_id, cc_identidad),
                        )
                        r = cur.fetchone()
                        base = _to_float(r[0]) if r else 0.0
                        nuevo = base + total
                        cur.execute(
                            """
                            UPDATE HOJA_TRABAJO SET VALOR = ?
                            WHERE IDCONCEPTO = ? AND IDATRIBUTO = ? AND TRIM(IDENTIDADTERCERO) = TRIM(?)
                            """,
                            (str(nuevo), id_concepto, attr_id, cc_identidad),
                        )
                    if id_atr_razon and cc_nombre:
                        cur.execute(
                            "UPDATE HOJA_TRABAJO SET VALOR = ? WHERE IDCONCEPTO = ? AND IDATRIBUTO = ? AND TRIM(IDENTIDADTERCERO) = TRIM(?)",
                            (cc_nombre, id_concepto, id_atr_razon, cc_identidad),
                        )
                    if id_atr_direccion and direccion_empresa:
                        cur.execute(
                            "UPDATE HOJA_TRABAJO SET VALOR = ? WHERE IDCONCEPTO = ? AND IDATRIBUTO = ? AND TRIM(IDENTIDADTERCERO) = TRIM(?)",
                            (direccion_empresa, id_concepto, id_atr_direccion, cc_identidad),
                        )
                    if id_atr_tipo_documento:
                        cur.execute(
                            "UPDATE HOJA_TRABAJO SET VALOR = ? WHERE IDCONCEPTO = ? AND IDATRIBUTO = ? AND TRIM(IDENTIDADTERCERO) = TRIM(?)",
                            ("43", id_concepto, id_atr_tipo_documento, cc_identidad),
                        )
                else:
                    for attr_id, total in suma_por_attr.items():
                        insert_fila_hoja_trabajo(
                            cur, id_concepto, attr_id, idelemento, str(total), cc_identidad_padded
                        )
                    if id_atr_razon and cc_nombre:
                        insert_fila_hoja_trabajo(
                            cur, id_concepto, id_atr_razon, idelemento, cc_nombre, cc_identidad_padded
                        )
                    if id_atr_identidad:
                        insert_fila_hoja_trabajo(
                            cur, id_concepto, id_atr_identidad, idelemento, cc_identidad, cc_identidad_padded
                        )
                    if id_atr_direccion and direccion_empresa:
                        insert_fila_hoja_trabajo(
                            cur, id_concepto, id_atr_direccion, idelemento, direccion_empresa, cc_identidad_padded
                        )
                    if id_atr_tipo_documento:
                        insert_fila_hoja_trabajo(
                            cur, id_concepto, id_atr_tipo_documento, idelemento, "43", cc_identidad_padded
                        )

                identidades_a_eliminar = [i for i in identidades_agrupar if str(i).strip() != cc_identidad.strip()]
                if identidades_a_eliminar:
                    ph = ",".join(["?"] * len(identidades_a_eliminar))
                    cur.execute(
                        f"""
                        DELETE FROM HOJA_TRABAJO
                        WHERE IDCONCEPTO = ? AND TRIM(IDENTIDADTERCERO) IN ({ph})
                        """,
                        [id_concepto, *[str(i).strip() for i in identidades_a_eliminar]],
                    )
                return f"Se agruparon {len(identidades_agrupar)} registros en cuantías menores."
        except Exception as e:
            return str(e)

    def deshacer_agrupar_cuantias(self, concepto: ConceptoRef) -> str:
        legacy_concepto = self._legacy_concepto(concepto)
        if not isinstance(legacy_concepto, dict) or "codigo" not in legacy_concepto or "formato" not in legacy_concepto:
            return "Concepto debe ser un diccionario con 'codigo' y 'formato'"
        try:
            with transaccion_segura() as (_con, cur):
                id_concepto = consultar_id_concepto(
                    legacy_concepto["codigo"], legacy_concepto["formato"]
                )
                if id_concepto is None:
                    return f"Concepto no encontrado: {legacy_concepto['codigo']} - {legacy_concepto['formato']}"
                registros = fetch_undo_registros_por_tipo(cur, 0, id_concepto)
                if not registros:
                    return "No hay agrupaciones para deshacer en este concepto."
                total_registros = 0
                for undo_id, payload_blob in registros:
                    pl = _payload_undo_desde_blob(payload_blob)
                    cc_identidad = pl.get("cc_identidad", "").strip()
                    cc_existia = pl.get("cc_existia", False)
                    suma_restar = pl.get("suma_restar", {}) or {}
                    filas = pl.get("filas_restaurar", [])

                    if cc_existia:
                        _restar_sumas_por_atributo(
                            cur,
                            id_concepto=id_concepto,
                            identidad_base=cc_identidad,
                            sumas_por_attr=suma_restar,
                        )
                    else:
                        cur.execute(
                            "DELETE FROM HOJA_TRABAJO WHERE IDCONCEPTO = ? AND TRIM(IDENTIDADTERCERO) = TRIM(?)",
                            (id_concepto, cc_identidad),
                        )
                    idelemento = pl.get("idelemento")
                    identidades_restauradas = set()
                    for f in filas:
                        ident = (f.get("ident") or "").strip()
                        ident_padded = ident.ljust(20)
                        insert_fila_hoja_trabajo(
                            cur,
                            f.get("idc", id_concepto),
                            f.get("ida"),
                            f.get("ide", idelemento),
                            f.get("val", ""),
                            ident_padded,
                        )
                        if ident:
                            identidades_restauradas.add(ident)
                    total_registros += len(identidades_restauradas)
                    delete_undo_por_id(cur, undo_id)
                return f"Se devolvieron {total_registros} registro(s)."
        except Exception as e:
            return str(e)

    def obtener_terceros_a_numerar(
        self, concepto: ConceptoRef
    ) -> List[str]:
        legacy_concepto = self._legacy_concepto(concepto)
        try:
            con = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
            cur = con.cursor()

            _ids_tdoc, ids_tdoc_str = tupla_ids_tdoc_atributo()
            if not ids_tdoc_str:
                return []

            if isinstance(legacy_concepto, dict) and "codigo" in legacy_concepto and "formato" in legacy_concepto:
                id_concepto = consultar_id_concepto(
                    legacy_concepto["codigo"], legacy_concepto["formato"]
                )
                if id_concepto is None:
                    return []
            else:
                concepto_codigo = str(legacy_concepto)
                cur.execute(
                    """
                    SELECT FIRST 1 ID FROM CONCEPTOS WHERE CODIGO = ?
                    """,
                    (concepto_codigo,),
                )
                concepto_row = cur.fetchone()
                if not concepto_row:
                    return []
                id_concepto = concepto_row[0]

            cur.execute(
                f"""
                SELECT DISTINCT IDENTIDADTERCERO
                FROM HOJA_TRABAJO
                WHERE VALOR = '42'
                  AND IDATRIBUTO IN ({ids_tdoc_str})
                  AND IDCONCEPTO = ?
                ORDER BY IDENTIDADTERCERO
                """,
                (id_concepto,),
            )
            terceros_tdoc = cur.fetchall()
            if not terceros_tdoc:
                return []

            cur.close()
            con.close()
            return [t[0] for t in terceros_tdoc]
        except Exception:
            return []

    def numerar_nits_extranjeros(
        self, concepto: ConceptoRef
    ) -> str:
        legacy_concepto = self._legacy_concepto(concepto)
        try:
            with transaccion_segura() as (_con, cur):
                id_concepto, concepto_encontrado, error_concepto = _resolver_id_y_config_concepto(
                    legacy_concepto,
                    mensaje_error_invalid="Concepto debe ser un diccionario con 'codigo' y 'formato'",
                    mensaje_error_not_found="Concepto no encontrado",
                )
                if error_concepto:
                    return error_concepto
                if not id_concepto or not concepto_encontrado:
                    return "No se pudo resolver el concepto."

                base_consecutivo = concepto_encontrado.get("exterior_identidad", "").strip()
                nueva_razon_social = concepto_encontrado.get("exterior_nombre", "").strip()

                if not base_consecutivo:
                    return "El concepto no tiene configurado 'exterior_identidad' (número inicial del consecutivo)."

                if base_consecutivo.isdigit() and len(base_consecutivo) >= 3:
                    base_solo = base_consecutivo[:-3]
                else:
                    base_solo = base_consecutivo.rstrip("0123456789")
                    if not base_solo:
                        base_solo = base_consecutivo

                atributos_concepto = consultar_atributos_por_concepto(legacy_concepto)
                ids_atributos_a_modificar = []
                id_atr_razon_social = None

                for attr in atributos_concepto:
                    descripcion = str(attr[2] if len(attr) > 2 else "").upper()
                    if "NÚMERO DE IDENTIFICACIÓN" in descripcion or "NUMERO DE IDENTIFICACION" in descripcion:
                        ids_atributos_a_modificar.append(attr[0])
                    elif "RAZÓN SOCIAL" in descripcion or "RAZON SOCIAL" in descripcion:
                        id_atr_razon_social = attr[0]

                if not ids_atributos_a_modificar:
                    return "No se encontraron atributos con 'tipo de documento' o 'número de identificación' en el concepto."

                ids_tdoc, ids_tdoc_str = tupla_ids_tdoc_atributo()
                if not ids_tdoc_str:
                    return "No se encontraron atributos de tipo de documento."

                cur.execute(
                    f"""
                    SELECT DISTINCT IDENTIDADTERCERO, IDCONCEPTO
                    FROM HOJA_TRABAJO
                    WHERE VALOR = '42' AND IDATRIBUTO IN ({ids_tdoc_str}) AND IDCONCEPTO = ?
                    ORDER BY IDENTIDADTERCERO
                    """,
                    (id_concepto,),
                )
                terceros = cur.fetchall()
                if not terceros:
                    return "No se encontraron terceros con tipo de documento 42."

                cur.execute(
                    """
                    SELECT DISTINCT TRIM(IDENTIDADTERCERO)
                    FROM HOJA_TRABAJO
                    WHERE TRIM(IDENTIDADTERCERO) LIKE ? AND IDCONCEPTO = ?
                    ORDER BY TRIM(IDENTIDADTERCERO) DESC
                    """,
                    (f"{base_solo}%", id_concepto),
                )
                existentes = cur.fetchall()

                contador = 1
                if existentes:
                    max_num = 0
                    for ident in existentes:
                        ident_str = str(ident[0]).strip()
                        if ident_str.startswith(base_solo):
                            try:
                                sufijo = ident_str[len(base_solo):].strip()
                                if sufijo.isdigit():
                                    num = int(sufijo)
                                    if num > max_num:
                                        max_num = num
                            except ValueError:
                                continue
                    contador = max_num + 1

                snapshot_nits = []
                ids_atributos_str = ",".join(str(id_atr) for id_atr in ids_atributos_a_modificar)
                for tercero_row in terceros:
                    identidad_antigua = str(tercero_row[0] or "").strip()
                    valor_razon = ""
                    valor_ident = identidad_antigua
                    if id_atr_razon_social:
                        cur.execute(
                            "SELECT VALOR FROM HOJA_TRABAJO WHERE IDCONCEPTO = ? AND IDATRIBUTO = ? AND TRIM(IDENTIDADTERCERO) = TRIM(?)",
                            (id_concepto, id_atr_razon_social, identidad_antigua),
                        )
                        r = cur.fetchone()
                        valor_razon = str(r[0] or "").strip() if r else ""
                    cur.execute(
                        f"SELECT VALOR FROM HOJA_TRABAJO WHERE IDCONCEPTO = ? AND IDATRIBUTO IN ({ids_atributos_str}) AND TRIM(IDENTIDADTERCERO) = TRIM(?)",
                        (id_concepto, identidad_antigua),
                    )
                    r = cur.fetchone()
                    if r:
                        valor_ident = str(r[0] or "").strip()
                    snapshot_nits.append({"ant": identidad_antigua, "razon": valor_razon, "ident_val": valor_ident})
                payload_nits = json.dumps(
                    {
                        "base_solo": base_solo,
                        "contador_ini": contador,
                        "items": snapshot_nits,
                        "id_atr_razon": id_atr_razon_social,
                        "ids_atr_ident": [int(x) for x in ids_atributos_a_modificar],
                        "ids_tdoc": [int(x) for x in ids_tdoc if isinstance(x, (int, float)) and int(x) != -1],
                    },
                    ensure_ascii=False,
                )
                insert_undo_hoja_trabajo(cur, 1, id_concepto, payload_nits, date.today())

                actualizados = 0

                for tercero_row in terceros:
                    identidad_antigua_raw = str(tercero_row[0])
                    nueva_identidad = f"{base_solo}{contador:03d}"
                    nueva_identidad_padded = nueva_identidad.ljust(20)

                    cur.execute(
                        """
                        UPDATE HOJA_TRABAJO
                        SET IDENTIDADTERCERO = ?
                        WHERE IDENTIDADTERCERO = ? AND IDCONCEPTO = ?
                        """,
                        (nueva_identidad_padded, identidad_antigua_raw, id_concepto),
                    )

                    cur.execute(
                        f"""
                        UPDATE HOJA_TRABAJO
                        SET VALOR = ?
                        WHERE IDENTIDADTERCERO = ? AND IDCONCEPTO = ? AND IDATRIBUTO IN ({ids_atributos_str})
                        """,
                        (nueva_identidad_padded, nueva_identidad_padded, id_concepto),
                    )

                    cur.execute(
                        f"""
                        UPDATE HOJA_TRABAJO
                        SET VALOR = '43'
                        WHERE IDENTIDADTERCERO = ? AND IDCONCEPTO = ? AND IDATRIBUTO IN ({ids_tdoc_str})
                        """,
                        (nueva_identidad_padded, id_concepto),
                    )

                    if id_atr_razon_social and nueva_razon_social:
                        cur.execute(
                            """
                            UPDATE HOJA_TRABAJO
                            SET VALOR = ?
                            WHERE IDENTIDADTERCERO = ? AND IDCONCEPTO = ? AND IDATRIBUTO = ?
                            """,
                            (
                                nueva_razon_social,
                                nueva_identidad_padded,
                                id_concepto,
                                id_atr_razon_social,
                            ),
                        )

                    contador += 1
                    actualizados += 1

                return f"Se numeraron {actualizados} identidades extranjeras correctamente."

        except Exception as e:
            return f"Error: {e}"

    def deshacer_numerar_nits(self, concepto: ConceptoRef) -> str:
        legacy_concepto = self._legacy_concepto(concepto)
        if not isinstance(legacy_concepto, dict) or "codigo" not in legacy_concepto or "formato" not in legacy_concepto:
            return "Concepto debe ser un diccionario con 'codigo' y 'formato'"
        try:
            with transaccion_segura() as (_con, cur):
                id_concepto = consultar_id_concepto(
                    legacy_concepto["codigo"], legacy_concepto["formato"]
                )
                if id_concepto is None:
                    return f"Concepto no encontrado: {legacy_concepto['codigo']} - {legacy_concepto['formato']}"
                registros = fetch_undo_registros_por_tipo(cur, 1, id_concepto)
                if not registros:
                    return "No hay numeraciones para deshacer en este concepto."
                total_registros = 0
                for undo_id, payload_blob in registros:
                    pl = _payload_undo_desde_blob(payload_blob)
                    base_solo = pl.get("base_solo", "")
                    contador_ini = int(pl.get("contador_ini", 1))
                    items = pl.get("items", [])
                    id_atr_razon = pl.get("id_atr_razon")
                    ids_atr_ident = pl.get("ids_atr_ident", []) or []
                    ids_tdoc = pl.get("ids_tdoc", []) or []
                    ids_tdoc_str = _ids_csv(ids_tdoc)
                    ids_atr_ident_str = _ids_csv(ids_atr_ident)

                    for i, it in enumerate(items):
                        ant = (it.get("ant") or "").strip()
                        razon = it.get("razon") or ""
                        ident_val = (it.get("ident_val") or ant).strip()
                        nueva = f"{base_solo}{contador_ini + i:03d}"
                        nueva_padded = nueva.ljust(20)
                        ant_padded = ant.ljust(20)

                        cur.execute(
                            "UPDATE HOJA_TRABAJO SET IDENTIDADTERCERO = ? WHERE IDENTIDADTERCERO = ? AND IDCONCEPTO = ?",
                            (ant_padded, nueva_padded, id_concepto),
                        )
                        if ids_atr_ident:
                            cur.execute(
                                f"UPDATE HOJA_TRABAJO SET VALOR = ? WHERE IDCONCEPTO = ? AND IDATRIBUTO IN ({ids_atr_ident_str}) AND TRIM(IDENTIDADTERCERO) = TRIM(?)",
                                (ident_val, id_concepto, ant),
                            )
                        if ids_tdoc:
                            cur.execute(
                                f"UPDATE HOJA_TRABAJO SET VALOR = '42' WHERE IDCONCEPTO = ? AND IDATRIBUTO IN ({ids_tdoc_str}) AND TRIM(IDENTIDADTERCERO) = TRIM(?)",
                                (id_concepto, ant),
                            )
                        if id_atr_razon and razon is not None:
                            cur.execute(
                                "UPDATE HOJA_TRABAJO SET VALOR = ? WHERE IDCONCEPTO = ? AND IDATRIBUTO = ? AND TRIM(IDENTIDADTERCERO) = TRIM(?)",
                                (razon, id_concepto, id_atr_razon, ant),
                            )
                    total_registros += len(items)
                    delete_undo_por_id(cur, undo_id)
                return f"Se devolvieron {total_registros} registro(s)."
        except Exception as e:
            return str(e)

    def deshacer_unificar(self, concepto: ConceptoRef) -> str:
        legacy_concepto = self._legacy_concepto(concepto)
        if not isinstance(legacy_concepto, dict) or "codigo" not in legacy_concepto or "formato" not in legacy_concepto:
            return "Concepto debe ser un diccionario con 'codigo' y 'formato'"
        try:
            with transaccion_segura() as (_con, cur):
                id_concepto = consultar_id_concepto(
                    legacy_concepto["codigo"], legacy_concepto["formato"]
                )
                if id_concepto is None:
                    return f"Concepto no encontrado: {legacy_concepto['codigo']} - {legacy_concepto['formato']}"
                registros = fetch_undo_registros_por_tipo(cur, 2, id_concepto)
                if not registros:
                    return "No hay unificaciones para deshacer en este concepto."
                total_registros = 0
                for undo_id, payload_blob in registros:
                    pl = _payload_undo_desde_blob(payload_blob)
                    base_id = str(pl.get("base_id", "") or "").strip()
                    sumas = pl.get("sumas", {}) or {}
                    filas = pl.get("filas_restaurar", [])
                    idelemento = pl.get("idelemento")

                    _restar_sumas_por_atributo(
                        cur,
                        id_concepto=id_concepto,
                        identidad_base=base_id,
                        sumas_por_attr=sumas,
                    )

                    identidades_restauradas = set()
                    for f in filas:
                        ident = (f.get("ident") or "").strip()
                        ident_raw = str(f.get("ident_raw", "") or "")
                        ident_insert = ident_raw if ident_raw else ident.ljust(20)
                        insert_fila_hoja_trabajo(
                            cur,
                            f.get("idc", id_concepto),
                            f.get("ida"),
                            f.get("ide", idelemento),
                            f.get("val", ""),
                            ident_insert,
                        )
                        if ident:
                            identidades_restauradas.add(ident)
                    total_registros += len(identidades_restauradas)
                    delete_undo_por_id(cur, undo_id)
                return f"Se devolvieron {total_registros} registro(s)."
        except Exception as e:
            return str(e)

    def crear_entrada_hoja_trabajo(self, datos: EntradaHojaPayload) -> bool:
        if "Concepto" not in datos:
            raise ValueError("El diccionario 'datos' debe contener la clave 'Concepto'")

        try:
            with transaccion_segura() as (_con, cur):
                codigo_concepto = datos["Concepto"]
                formato_concepto = datos.get("FORMATO", "")

                par_ce = _resolver_concepto_y_elemento_entrada(cur, codigo_concepto, formato_concepto)
                if par_ce is None:
                    return False
                concepto, elemento = par_ce

                if formato_concepto:
                    concepto_para_atributos = {
                        "codigo": codigo_concepto,
                        "formato": formato_concepto,
                    }
                else:
                    concepto_para_atributos = codigo_concepto

                atributos = consultar_atributos_por_concepto(concepto_para_atributos)

                for attr in atributos:
                    if len(attr) >= 5 and (attr[4] or 0) < 9000:
                        descripcion = attr[2] if len(attr) > 2 else None
                        if descripcion and descripcion in datos:
                            insert_fila_hoja_trabajo(
                                cur,
                                concepto,
                                attr[0],
                                elemento,
                                datos[descripcion],
                                datos.get("Número de Identificación"),
                            )
            return True
        except Exception:
            return False

    def actualizar_entrada_hoja_trabajo(
        self, id_concepto: int, identidad: str, datos: EntradaHojaPayload
    ) -> bool:
        try:
            with transaccion_segura() as (_con, cur):
                codigo_concepto = datos["Concepto"]
                formato_concepto = datos.get("FORMATO", "")

                for llave, valor in datos.items():
                    if llave not in ("FORMATO", "Concepto", "id_concepto"):
                        _actualizar_valor_entrada_por_descripcion(
                            cur,
                            valor=valor,
                            id_concepto=id_concepto,
                            identidad=identidad,
                            codigo_concepto=str(codigo_concepto),
                            formato_concepto=str(formato_concepto),
                            descripcion=str(llave),
                        )
            return True
        except Exception:
            return False

    def eliminar_hoja_por_identidad(
        self,
        identidad: str,
        filtro: Optional[float] = None,
        campo_id: Optional[int] = None,
    ) -> Optional[Exception]:
        try:
            with transaccion_segura() as (_con, cur):
                if filtro is None or campo_id is None:
                    cur.execute(
                        """
                        DELETE FROM HOJA_TRABAJO WHERE TRIM(IDENTIDADTERCERO) = ?
                        """,
                        (identidad,),
                    )
                else:
                    cur.execute(
                        """
                        DELETE FROM HOJA_TRABAJO
                        WHERE TRIM(IDENTIDADTERCERO) IN (
                            SELECT DISTINCT TRIM(IDENTIDADTERCERO)
                            FROM HOJA_TRABAJO
                            WHERE TRIM(IDENTIDADTERCERO) = ?
                              AND IDATRIBUTO = ?
                              AND CAST(VALOR AS DECIMAL(18, 2)) < ?
                        )
                        """,
                        (identidad, campo_id, filtro),
                    )
            return None
        except Exception as e:
            return e

    def eliminar_hoja_por_concepto(
        self,
        concepto: ConceptoRef,
        filtro: Optional[float] = None,
        campo_id: Optional[int] = None,
    ) -> Optional[Exception]:
        legacy_concepto = self._legacy_concepto(concepto)
        id_concepto = resolver_id_concepto_legacy(legacy_concepto)
        if id_concepto is None:
            return None

        try:
            with transaccion_segura() as (_con, cur):
                delete_hoja_trabajo_por_id_concepto_cursor(
                    cur, id_concepto, filtro, campo_id
                )
            return None
        except Exception as e:
            return e

    def obtener_valores_fideicomiso_existentes(
        self, concepto: ConceptoRef
    ) -> Dict[str, List[str]]:
        vacio: Dict[str, List[str]] = {"tipo": [], "subtipo": []}
        legacy_concepto = self._legacy_concepto(concepto)
        if not isinstance(legacy_concepto, dict) or "codigo" not in legacy_concepto or "formato" not in legacy_concepto:
            return vacio

        try:
            id_concepto = consultar_id_concepto(
                legacy_concepto["codigo"], legacy_concepto["formato"]
            )
            id_t, id_s = _ids_atributos_fideicomiso(legacy_concepto)
            if not id_concepto or not id_t or not id_s:
                return vacio

            with transaccion_segura() as (_con, cur):
                return {
                    "tipo": _distinct_valores_hoja_atributo(cur, id_concepto, id_t),
                    "subtipo": _distinct_valores_hoja_atributo(cur, id_concepto, id_s),
                }
        except Exception:
            return vacio

    def actualizar_fideicomiso_masivo(
        self,
        concepto: ConceptoRef,
        tipo_fideicomiso: str,
        subtipo_fideicomiso: str,
        filtro_tipo_actual: str = "",
        filtro_subtipo_actual: str = "",
    ) -> str:
        legacy_concepto = self._legacy_concepto(concepto)
        if not isinstance(legacy_concepto, dict) or "codigo" not in legacy_concepto or "formato" not in legacy_concepto:
            return "Concepto inválido: se requiere código y formato."

        tipo_val = str(tipo_fideicomiso or "").strip()
        subtipo_val = str(subtipo_fideicomiso or "").strip()
        if not tipo_val or not subtipo_val:
            return "Debe seleccionar tipo y subtipo de fideicomiso."

        filtro_tipo_val = str(filtro_tipo_actual or "").strip()
        filtro_subtipo_val = str(filtro_subtipo_actual or "").strip()

        try:
            id_concepto = consultar_id_concepto(
                legacy_concepto["codigo"], legacy_concepto["formato"]
            )
            id_t, id_s = _ids_atributos_fideicomiso(legacy_concepto)
            if not id_concepto:
                return f"Concepto no encontrado: {legacy_concepto['codigo']} - {legacy_concepto['formato']}"
            if not id_t or not id_s:
                return "El concepto no tiene atributos de tipo/subtipo de fideicomiso."

            with transaccion_segura() as (_con, cur):
                if not filtro_tipo_val and not filtro_subtipo_val:
                    for val, id_a in ((tipo_val, id_t), (subtipo_val, id_s)):
                        cur.execute(
                            """
                            UPDATE HOJA_TRABAJO
                            SET VALOR = ?
                            WHERE IDCONCEPTO = ? AND IDATRIBUTO = ?
                            """,
                            (val, id_concepto, id_a),
                        )
                    return "Tipo y subtipo de fideicomiso actualizados correctamente."

                objetivo = set()
                if filtro_tipo_val:
                    objetivo = _identidades_con_valor_atributo(
                        cur, id_concepto, id_t, filtro_tipo_val
                    )
                if filtro_subtipo_val:
                    sub_set = _identidades_con_valor_atributo(
                        cur, id_concepto, id_s, filtro_subtipo_val
                    )
                    objetivo = sub_set if not objetivo else objetivo.intersection(sub_set)

                if not objetivo:
                    return "No se encontraron identidades que cumplan los filtros especificados."

                _update_hoja_valor_por_identidades(
                    cur, tipo_val, id_concepto, id_t, list(objetivo)
                )
                _update_hoja_valor_por_identidades(
                    cur, subtipo_val, id_concepto, id_s, list(objetivo)
                )

            return "Tipo y subtipo de fideicomiso actualizados correctamente."
        except Exception:
            return "Error actualizando tipo/subtipo de fideicomiso."
