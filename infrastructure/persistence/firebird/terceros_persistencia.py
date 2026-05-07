"""TERCEROS en EX por empresa en sesión: listado paginado, importación desde producto y CRUD."""
from typing import Any, Dict, List, Optional, Tuple, Union

from core import session
from core.catalogues import TIPOSDOC
from core.settings import PERIODO
from infrastructure.adapters.helisa_firebird import CNX_BDHelisa
from infrastructure.adapters.proteccion_firebird import transaccion_segura
from infrastructure.persistence.firebird.elementos_persistencia import (
    consultar_atributos_hoja_tercero_en_cursor,
)


def _notificar_error(operacion: str, cause: BaseException) -> None:
    print(f"TERCEROS ({operacion}): {cause}")


# Atributos de HOJA_TRABAJO enlazados a columnas del formulario de tercero (sufijo lógico en BD).
MAPEO_CAMPO_TERCERO_A_ATRIBUTO_HOJA = {
    "tipodocumento": "tdoc",
    "digitoverificacion": "dv",
    "razonsocial": "raz",
    "primerapellido": "ap1",
    "segundoapellido": "ap2",
    "primernombre": "nom1",
    "segundonombre": "nom2",
    "direccion": "dir",
    "departamento": "coddepto",
    "municipio": "mun",
    "pais": "pais",
}


def _codigo_empresa_sesion() -> int:
    return session.EMPRESA_ACTUAL["codigo"]


def _cache_nombres_tipodocumento() -> Dict[Any, str]:
    cache: Dict[Any, str] = {}
    for codigo, datos in TIPOSDOC.items():
        nombre = datos[1] if datos and len(datos) >= 2 else None
        if nombre is not None:
            cache[codigo] = nombre
            cache[str(codigo)] = nombre
    return cache


def _fila_tercero_select_star_a_dict(fila: tuple, tipodoc_por_codigo: Dict[Any, str]) -> Dict[str, Any]:
    (
        id_interno,
        cod_tipo_doc,
        identidad,
        naturaleza,
        digito_verif,
        razon_social,
        apellido1,
        apellido2,
        nombre1,
        nombre2,
        direccion,
        departamento,
        municipio,
        pais,
    ) = fila
    texto_tipo = (
        (tipodoc_por_codigo.get(cod_tipo_doc) or tipodoc_por_codigo.get(str(cod_tipo_doc)) or str(cod_tipo_doc).strip())
        if cod_tipo_doc is not None
        else ""
    )
    return {
        "id": str(id_interno).strip(),
        "tipodocumento": texto_tipo,
        "identidad": identidad,
        "naturaleza": naturaleza,
        "digitoverificacion": digito_verif,
        "razonsocial": razon_social,
        "primerapellido": apellido1,
        "segundoapellido": apellido2,
        "primernombre": nombre1,
        "segundonombre": nombre2,
        "direccion": direccion,
        "departamento": departamento,
        "municipio": municipio,
        "pais": pais,
    }


def _total_desde_count(cursor, sql: str, params: tuple) -> int:
    cursor.execute(sql, params)
    fila = cursor.fetchone()
    return int(fila[0]) if fila and fila[0] is not None else 0


def _armar_sql_y_parametros_listado(
    filtro: Optional[Union[str, List[str]]],
    offset: int,
    limit: int,
) -> Tuple[str, List[Any], str, List[Any]]:
    """Devuelve (sql_count, params_count, sql_page, params_page)."""
    if filtro:
        if isinstance(filtro, list) and len(filtro) > 0 and filtro[0] == "DIVIDIR":
            where = "WHERE naturaleza = 0 AND tipodocumento != 31"
            params_count: List[Any] = []
            if len(filtro) > 1:
                texto = str(filtro[1]).strip()
                patron_razon = f"%{texto}%"
                patron_ident = f"%{texto}%"
                where += " AND (UPPER(razonsocial) LIKE UPPER(?) OR UPPER(identidad) LIKE UPPER(?))"
                params_count.extend([patron_razon, patron_ident])
            sql_count = f"SELECT COUNT(*) FROM TERCEROS {where}"
            sql_page = f"""
                SELECT FIRST ? SKIP ? *
                FROM TERCEROS
                {where}
                ORDER BY razonsocial
            """
            params_page = [limit, offset] + params_count
            return sql_count, params_count, sql_page, params_page

        base = filtro[0] if isinstance(filtro, list) else filtro
        texto = str(base).strip()
        patron_razon = f"%{texto}%"
        patron_ident = f"%{texto}%"
        params_both = [patron_razon, patron_ident]
        sql_count = """
            SELECT COUNT(*)
            FROM TERCEROS
            WHERE UPPER(razonsocial) LIKE UPPER(?)
               OR UPPER(identidad) LIKE UPPER(?)
        """
        sql_page = """
            SELECT FIRST ? SKIP ? *
            FROM TERCEROS
            WHERE UPPER(razonsocial) LIKE UPPER(?)
               OR UPPER(identidad) LIKE UPPER(?)
            ORDER BY razonsocial
        """
        params_page = [limit, offset, patron_razon, patron_ident]
        return sql_count, params_both, sql_page, params_page

    sql_count = "SELECT COUNT(*) FROM TERCEROS"
    sql_page = "SELECT FIRST ? SKIP ? * FROM TERCEROS ORDER BY razonsocial"
    return sql_count, [], sql_page, [limit, offset]


def obtener_terceros(
    offset: int = 0,
    limit: int = 10,
    filtro: Optional[Union[str, List[str]]] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    if offset < 0 or limit < 0:
        raise ValueError("offset y limit deben ser valores no negativos")

    try:
        conexion = CNX_BDHelisa("EX", _codigo_empresa_sesion(), "sysdba")
        cursor = conexion.cursor()
        sql_count, params_count, sql_page, params_page = _armar_sql_y_parametros_listado(
            filtro, offset, limit
        )
        total = _total_desde_count(cursor, sql_count, tuple(params_count))
        cursor.execute(sql_page, params_page)
        filas = cursor.fetchall()
        cursor.close()
        conexion.close()
    except Exception as exc:
        _notificar_error("obtener listado paginado", exc)
        return [], 0

    tipodoc_por_codigo = _cache_nombres_tipodocumento()
    return (
        [_fila_tercero_select_star_a_dict(fila, tipodoc_por_codigo) for fila in filas],
        total,
    )


def obtener_terceros_producto(codigo: int, producto: str) -> int:
    try:
        conexion = CNX_BDHelisa(producto, codigo, "sysdba")
        cursor = conexion.cursor()
        tabla_tema = f"TEMA{PERIODO}"
        cursor.execute(
            f"""
            select decode(ma.clase,
                            'C', '13', 'A', '31', 'X', '22', 'T', '12',
                            'R', '11', 'E', '21', 'P', '41', 'F', '42',
                            'D', '42', 'I', '50', 'S', '48', 'B', '47',
                            'U', '91', 'H', '43'
                    ) as tipo_documento, ma.identidad, ma.nombre razon_social,
                    xx.apellido1, xx.apellido2, xx.nombre1, xx.nombre2, ma.direccion,
                    cx.codigo_dian municipio, cx.codigo_departamento, px.codigo pais, ma.verificacion,
                    ma.naturaleza
            from {tabla_tema} ma
            left join temaxxxx xx on ma.identidad = xx.identidad
            left join ciudxxxx cx on ma.ciudad = cx.codigo
            left join paisxxxx px on cx.cod_pais = px.codigo
        """
        )
        filas = cursor.fetchall()
        cursor.close()
        conexion.close()
    except Exception as exc:
        print(f"[ERROR] TERCEROS producto: {exc}")
        return 0

    if not filas:
        return 0
    insertados = crear_tercero(filas, codigo, desde_producto=True)
    return insertados if isinstance(insertados, int) else 0


def _tuplas_desde_bloque_producto(tercero: Any) -> List[tuple]:
    if len(tercero) == 0:
        return []
    if isinstance(tercero[0], (list, tuple)):
        return list(tercero)
    return [tercero]


def _parametros_insert_fila_producto(fila: tuple) -> tuple:
    (
        tipo_documento,
        identidad,
        razon_social,
        apellido1,
        apellido2,
        nombre1,
        nombre2,
        direccion,
        municipio,
        codigo_departamento,
        pais,
        verificacion,
        naturaleza,
    ) = fila
    return (
        int(tipo_documento) if tipo_documento else 0,
        identidad,
        int(naturaleza),
        verificacion if verificacion else "",
        razon_social.strip() if razon_social else "",
        apellido1,
        apellido2,
        nombre1,
        nombre2,
        direccion,
        int(municipio) if municipio else 0,
        int(codigo_departamento) if codigo_departamento else 0,
        int(pais) if pais else 0,
    )


def crear_tercero(
    tercero: Any,
    codigo: int,
    *,
    desde_producto: bool = False,
) -> Union[str, bool, int]:
    if desde_producto:
        filas = _tuplas_desde_bloque_producto(tercero)
        if not filas:
            return 0
        try:
            with transaccion_segura(codigo) as (_con, cursor):
                for fila in filas:
                    cursor.execute(
                        """
                        INSERT INTO TERCEROS (
                            TipoDocumento, Identidad, naturaleza, DigitoVerificacion,
                            RazonSocial, PrimerApellido, SegundoApellido,
                            PrimerNombre, SegundoNombre, Direccion,
                            Municipio, Departamento, Pais
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        _parametros_insert_fila_producto(fila),
                    )
            return len(filas)
        except Exception as exc:
            _notificar_error("import masivo desde producto", exc)
            return 0

    if not isinstance(tercero, dict):
        raise ValueError("En modo normal, 'tercero' debe ser un diccionario.")

    try:
        with transaccion_segura() as (_con, cursor):
            cursor.execute(
                """
                SELECT COUNT(*) FROM TERCEROS
                WHERE IDENTIDAD = ? AND TIPODOCUMENTO = ?
                """,
                (
                    tercero.get("identidad"),
                    tercero.get("tipodocumento"),
                ),
            )
            if cursor.fetchone()[0] > 0:
                return "Error: ya existe un tercero con esa identidad y tipo de documento."

            cursor.execute(
                """
                INSERT INTO TERCEROS (
                    IDENTIDAD, TIPODOCUMENTO, NATURALEZA, RAZONSOCIAL,
                    PRIMERAPELLIDO, SEGUNDOAPELLIDO,
                    PRIMERNOMBRE, SEGUNDONOMBRE,
                    DIRECCION, DEPARTAMENTO, MUNICIPIO, PAIS
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tercero.get("identidad"),
                    tercero.get("tipodocumento"),
                    tercero.get("naturaleza"),
                    tercero.get("razonsocial"),
                    tercero.get("primerapellido"),
                    tercero.get("segundoapellido"),
                    tercero.get("primernombre"),
                    tercero.get("segundonombre"),
                    tercero.get("direccion"),
                    tercero.get("departamento"),
                    tercero.get("municipio"),
                    tercero.get("pais"),
                ),
            )
        return "Tercero creado correctamente."
    except Exception as exc:
        _notificar_error("insert manual", exc)
        return False


def actualizar_tercero(tercero: Dict[str, Any]) -> Union[str, bool]:
    if "id" not in tercero:
        raise ValueError("El diccionario 'tercero' debe contener la clave 'id'")

    try:
        with transaccion_segura() as (_con, cursor):
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM TERCEROS
                WHERE IDENTIDAD = ?
                    AND TIPODOCUMENTO = ?
                    AND ID <> ?
                """,
                (
                    tercero.get("identidad"),
                    tercero.get("tipodocumento"),
                    tercero.get("id"),
                ),
            )
            if cursor.fetchone()[0] > 0:
                return "Error: ya existe otro tercero con esa identidad y tipo de documento."

            cursor.execute(
                """
                UPDATE TERCEROS
                SET
                    TIPODOCUMENTO = ?,
                    NATURALEZA = ?,
                    RAZONSOCIAL = ?,
                    PRIMERAPELLIDO = ?,
                    SEGUNDOAPELLIDO = ?,
                    PRIMERNOMBRE = ?,
                    SEGUNDONOMBRE = ?,
                    DIRECCION = ?,
                    DEPARTAMENTO = ?,
                    MUNICIPIO = ?,
                    PAIS = ?
                WHERE ID = ?
                """,
                (
                    tercero.get("tipodocumento"),
                    tercero.get("naturaleza"),
                    tercero.get("razonsocial"),
                    tercero.get("primerapellido"),
                    tercero.get("segundoapellido"),
                    tercero.get("primernombre"),
                    tercero.get("segundonombre"),
                    tercero.get("direccion"),
                    tercero.get("departamento"),
                    tercero.get("municipio"),
                    tercero.get("pais"),
                    tercero.get("id"),
                ),
            )

            identidad = tercero.get("identidad")
            for clave_formulario, valor in tercero.items():
                if clave_formulario not in {"id", "identidad", "naturaleza"}:
                    nombre_attr = MAPEO_CAMPO_TERCERO_A_ATRIBUTO_HOJA.get(clave_formulario)
                    if not nombre_attr:
                        continue
                    for atributo in consultar_atributos_hoja_tercero_en_cursor(
                        cursor, identidad, nombre_attr
                    ):
                        cursor.execute(
                            """
                            UPDATE HOJA_TRABAJO
                            SET VALOR = ?
                            WHERE IDENTIDADTERCERO = ? AND IDATRIBUTO = ?
                            """,
                            (valor, identidad, atributo[0]),
                        )
        return "Tercero actualizado correctamente."
    except Exception as exc:
        _notificar_error("update", exc)
        return False


def eliminar_tercero(identidad: str) -> Union[bool, Exception]:
    try:
        with transaccion_segura() as (_con, cursor):
            cursor.execute(
                "SELECT COUNT(*) FROM HOJA_TRABAJO WHERE IDENTIDADTERCERO = ?",
                (identidad,),
            )
            if cursor.fetchone()[0] > 0:
                return False
            cursor.execute("DELETE FROM TERCEROS WHERE IDENTIDAD = ?", (identidad,))
        return True
    except Exception as exc:
        _notificar_error("delete", exc)
        return exc
