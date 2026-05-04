"""
Persistencia Firebird: tabla EMPRESAS (población desde productos, listado, ficha, actualización).
"""
from typing import List, Dict, Any, Optional
from infrastructure.adapters.helisa_firebird import CNX_BDHelisa
from infrastructure.adapters.proteccion_firebird import transaccion_segura
from core.settings import PERIODO
from core.catalogues import obtener_codigo_departamento_desde_municipio


def poblar_empresas_desde_productos() -> None:
    """
    Carga todas las empresas del año gravable desde DIRECTOR de NI/PH
    hacia la tabla EMPRESAS de la BD global EX.
    Se invoca al crear la BD global tras ``bd_constructor.Empresas`` (vía ``fn_bd_helisa``).
    """
    periodo = int(PERIODO)
    try:
        with transaccion_segura(codigo_empresa=-1) as (conn, cur_ex):
            for producto, campo_codigo in (("NI", "CodigoEmpresaNI"), ("PH", "CodigoEmpresaPH")):
                try:
                    print(f"[EMPRESAS] Poblando desde producto {producto}")
                    con_p = CNX_BDHelisa(producto, -1, "sysdba")
                    if not con_p:
                        continue
                    cur_p = con_p.cursor()
                    cur_p.execute("""
                        SELECT d.CODIGO, d.NOMBRE, d.IDENTIDAD, d.DIRECCION, d.CODIGO_CIUDAD,
                               c.CODIGO_DEPARTAMENTO, c.COD_PAIS
                        FROM DIRECTOR d
                        LEFT JOIN CIUDADES c ON c.CODIGO = d.CODIGO_CIUDAD
                        WHERE ? BETWEEN d.ANOINICIO AND d.ANOACTUAL
                        ORDER BY d.NOMBRE
                    """, (periodo,))
                    to_n = lambda v: None if v in (None, "") else v
                    for codigo, nombre, identidad, direccion, ciudad, depto, pais in cur_p.fetchall():
                        if depto is None and ciudad is not None:
                            cod_depto = obtener_codigo_departamento_desde_municipio(ciudad)
                            depto = int(cod_depto) if cod_depto is not None else None
                        mun = str(ciudad)[2:] if ciudad and len(str(ciudad)) >= 3 else ciudad
                        cur_ex.execute(f"""
                            UPDATE OR INSERT INTO EMPRESAS
                                (Identidad, Nombre, {campo_codigo}, Direccion, Municipio, Departamento, Pais)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            MATCHING (Identidad)
                        """, (identidad, nombre, codigo, direccion, to_n(mun), to_n(depto), to_n(pais)))
                    cur_p.close()
                    con_p.close()
                    print(f"[EMPRESAS] Pobladas desde producto {producto}")
                except Exception as e:
                    print(f"Error poblando EMPRESAS desde producto {producto}: {e}")
    except Exception as e:
        print(f"Error poblando EMPRESAS en BD global: {e}")


def obtener_empresas(producto: str) -> List[Dict[str, Any]]:
    """
    Obtiene lista de empresas desde la BD global (EX).
    No vuelve a leer DIRECTOR/CIUDADES; asume que el cargue inicial
    ya se hizo al crear la BD.
    """
    if producto not in ("NI", "PH"):
        return []

    empresas: List[Dict[str, Any]] = []
    try:
        con = CNX_BDHelisa("EX", -1, "sysdba")
        if con is None:
            raise ConnectionError("No se pudo conectar a la BD global (EX)")
        cur = con.cursor()
        if producto == "NI":
            cur.execute("""
                SELECT CodigoEmpresaNI, Nombre, Identidad
                FROM EMPRESAS
                WHERE CodigoEmpresaNI IS NOT NULL
                ORDER BY Nombre
            """)
        else:
            cur.execute("""
                SELECT CodigoEmpresaPH, Nombre, Identidad
                FROM EMPRESAS
                WHERE CodigoEmpresaPH IS NOT NULL
                ORDER BY Nombre
            """)
        empresas = [
            {"codigo": c, "nombre": n, "identidad": i}
            for c, n, i in cur.fetchall()
        ]
        cur.close()
        con.close()
    except Exception as e:
        print(f"Error obteniendo empresas desde BD global para producto {producto}: {e}")
        # Fallback: leer directamente del producto (NI/PH) para no bloquear
        # el flujo de activación cuando EX no está configurada aún.
        try:
            con_p = CNX_BDHelisa(producto, -1, "sysdba")
            if con_p is None:
                raise ConnectionError(f"No se pudo conectar a BD de producto {producto}")
            cur_p = con_p.cursor()
            cur_p.execute(
                """
                SELECT d.CODIGO, d.NOMBRE, d.IDENTIDAD
                FROM DIRECTOR d
                WHERE ? BETWEEN d.ANOINICIO AND d.ANOACTUAL
                ORDER BY d.NOMBRE
                """,
                (int(PERIODO),),
            )
            empresas = [
                {"codigo": c, "nombre": n, "identidad": i}
                for c, n, i in cur_p.fetchall()
            ]
            cur_p.close()
            con_p.close()
            return empresas
        except Exception as e2:
            print(f"Error obteniendo empresas desde producto {producto}: {e2}")
            return []
    return empresas


def obtener_info_empresa(producto: str, codigo_empresa: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene información detallada de una empresa. Lee primero desde la BD central (EX);
    si no hay datos o falla, lee desde el producto (DIRECTOR + CIUDADES).
    """
    # Intentar desde BD central
    try:
        con_ex = CNX_BDHelisa("EX", -1, "sysdba")
        cur_ex = con_ex.cursor()
        if producto == "NI":
            cur_ex.execute("""
                SELECT Identidad, Nombre, Direccion, Municipio, Departamento, Pais
                FROM EMPRESAS WHERE CodigoEmpresaNI = ?
            """, (codigo_empresa,))
        else:
            cur_ex.execute("""
                SELECT Identidad, Nombre, Direccion, Municipio, Departamento, Pais
                FROM EMPRESAS WHERE CodigoEmpresaPH = ?
            """, (codigo_empresa,))
        row = cur_ex.fetchone()
        cur_ex.close()
        con_ex.close()
        if row:
            municipio, depto, pais = row[3], row[4], row[5]
            if depto is None and municipio is not None:
                cod_depto = obtener_codigo_departamento_desde_municipio(municipio)
                depto = int(cod_depto) if cod_depto else None
            def _norm_int(x):
                if x is None:
                    return None
                try:
                    return int(x)
                except (ValueError, TypeError):
                    return x
            data = {
                "codigo": codigo_empresa,
                "nombre": row[1],
                "identidad": row[0],
                "direccion": row[2] or "",
                "municipio": _norm_int(municipio),
                "departamento": _norm_int(depto),
                "pais": _norm_int(pais),
            }
            return data
    except Exception:
        pass
    return "Error obteniendo información de la empresa"


def actualizar_info_empresa(identidad: str, direccion: Optional[str], codigo_ciudad: Optional[str],
                            codigo_departamento: Optional[str], codigo_pais: Optional[str]) -> bool:
    """
    Actualiza dirección y códigos de ciudad/departamento/país en la BD central.
    Mismo criterio que actualizar_tercero: códigos se envían como int (o None si vacío)
    para que la BD persista igual que en Terceros (columnas dmEntero004).
    """
    def _a_int(v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None
    cod_ciu = _a_int(codigo_ciudad)
    cod_depto = _a_int(codigo_departamento)
    cod_pais = _a_int(codigo_pais)
    args = (direccion or None, cod_ciu, cod_depto, cod_pais, identidad)
    try:
        with transaccion_segura(codigo_empresa=-1) as (conn, cur):
            cur.execute("""
                UPDATE EMPRESAS SET Direccion = ?, Municipio = ?, Departamento = ?, Pais = ?
                WHERE Identidad = ?
            """, args)
            return getattr(cur, "rowcount", -999) > 0
    except Exception as e:
        print(f"Error actualizando información de empresa: {e}")
        return False
