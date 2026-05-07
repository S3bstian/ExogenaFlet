"""Autenticación, usuarios, traducción de catálogos, restauración de BD Helisa y columnas tipo activo S/N."""
from typing import Optional, Tuple, Any
import secrets
import string
import os
from infrastructure.adapters.helisa_firebird import (
    CNX_BDHelisa,
    RW_Helisa,
    crearBD_Particular,
)
from infrastructure.adapters.proteccion_firebird import (
    hacer_backup_bd,
    proceso_protegido,
    transaccion_segura,
)
from core import session
from core.settings import PERIODO


# Whitelist de tablas permitidas para traductor_cod
TABLAS_PERMITIDAS = {
    # Tablas BD global
    "TIPOSDOCUMENTOS",
    "DEPARTAMENTO",
    "MUNICIPIO",
    "PAIS",
    "CIUDADES",
    "NATURALEZAS",
    # Tablas BD particular
    "ACUMULADOS",
    "ATRIBUTOS",
    "BANCOS_MOV",
    "CONCEPTOS",
    "CONSORCIOS",
    "CUENTAS_ATRIBUTOS",
    "CUENTAS_CONT",
    "CUENTAS_TRIB",
    "ELEMENTOS",
    "FORMAACUMULADO",
    "FORMATOS",
    "HOJA_TRABAJO",
    "PRODUCTOS",
    "TERCEROS",
    "TERCEROS_MOV_CONT",
    "TERCEROS_MOV_TRIB",
}


def generar_clave(longitud: int = 12) -> str:
    caracteres_permitidos = string.ascii_letters + string.digits
    return "".join(secrets.choice(caracteres_permitidos) for _ in range(longitud))


def autenticar_usuario(nombre: str, clave: str) -> Optional[Tuple[int, str]]:
    try:
        conexion = CNX_BDHelisa("EX", -1, "sysdba")
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT id, nombre FROM USUARIOS WHERE nombre = ? AND clave = ? AND activo = 'S'",
            (nombre, clave),
        )
        resultado = cursor.fetchone()
        cursor.close()
        conexion.close()
        return resultado
    except Exception as exc:
        print(f"Error obteniendo el usuario: {exc}")
        return None


def obtener_usuarios() -> list[Tuple[int, str, str, str]]:
    try:
        conexion = CNX_BDHelisa("EX", -1, "sysdba")
        cursor = conexion.cursor()
        cursor.execute("SELECT Id, Nombre, Email, activo FROM USUARIOS")
        data = cursor.fetchall()
        cursor.close()
        conexion.close()
        return data
    except Exception as exc:
        print(f"Error obteniendo usuarios: {exc}")
        return []


def crear_usuario(usuario_id: Optional[int], nombre: str, email: str) -> bool:
    try:
        with transaccion_segura(codigo_empresa=-1) as (_conn, cur):
            # Limpieza de valores
            nombre = nombre.strip()
            email = email.strip()
            
            # Validación básica
            if not nombre or not email:
                print("Error: nombre y email son requeridos")
                return False
            
            # INSERT
            if usuario_id is None:
                # Verificar duplicado
                cur.execute(
                    """
                    SELECT COUNT(*) FROM USUARIOS
                    WHERE LOWER(TRIM(Nombre)) = LOWER(TRIM(?))
                       OR LOWER(TRIM(Email)) = LOWER(TRIM(?))
                    """,
                    (nombre, email)
                )
                existe = cur.fetchone()[0]
                if existe > 0:
                    print(f"Ya existe un usuario con el mismo nombre o email: {nombre}, {email}")
                    return False
                
                clave = generar_clave()
                
                cur.execute(
                    """
                    INSERT INTO USUARIOS (Nombre, Email, Clave, Activo)
                    VALUES (?, ?, ?, 'S')
                    """,
                    (nombre, email, clave)
                )
                return True
            cur.execute(
                """
                UPDATE USUARIOS
                SET Nombre = ?, Email = ?
                WHERE Id = ?
                """,
                (nombre, email, usuario_id),
            )
            return True
    except Exception as exc:
        print(f"Error guardando usuario: {exc}")
        return False


def obtener_codigos_traduccion(
    tabla: str, producto: str = "EX", codigo_empresa: int = -2
) -> Optional[list[Tuple[Any, ...]]]:
    """Obtiene códigos de traducción desde una tabla (PAIS, DEPARTAMENTO, MUNICIPIO, etc.)."""
    tabla_normalizada = tabla.upper().strip()
    if tabla_normalizada not in TABLAS_PERMITIDAS:
        raise ValueError(f"Tabla no permitida: {tabla}. Tablas permitidas: {', '.join(sorted(TABLAS_PERMITIDAS))}")
    try:
        con = CNX_BDHelisa(producto, codigo_empresa, "sysdba")
        if not con:
            return None
        cur = con.cursor()
        if tabla_normalizada == "TIPOSDOCUMENTOS":
            cur.execute("SELECT id, tipo, descripcion FROM TIPOSDOCUMENTOS")
        else:
            cur.execute(f"SELECT * FROM {tabla_normalizada} ORDER BY nombre")
        resultado = cur.fetchall()
        cur.close()
        con.close()
        return resultado
    except Exception as exc:
        print(f"Error al obtener {tabla}: {exc}")
        return None


def restaurar_base_datos(loader: Any, page: Optional[Any] = None) -> Optional[Exception]:
    """Elimina la BD EX de la empresa en sesión, con backup previo vía proceso_protegido, y la recrea."""
    codigo = session.EMPRESA_ACTUAL["codigo"]
    producto = session.EMPRESA_ACTUAL["producto"]
    
    # Proteger contra ejecuciones simultáneas
    with proceso_protegido("restaurar", f"Empresa {codigo} - {producto}"):
        try:
            # Crear backup antes de eliminar la BD
            backup_path = hacer_backup_bd(codigo)
            print(f"[RESTAURAR] Backup creado: {backup_path}")
        except Exception as e:
            print(f"[RESTAURAR] Advertencia: No se pudo crear backup: {e}")
            # Continuar de todas formas, pero informar al usuario
            
        # Cerrar conexión si está abierta
        try:
            con = CNX_BDHelisa("EX", codigo, "sysdba")
            if con:
                con.close()
        except Exception as e:
            print(f"[RESTAURAR] Advertencia al cerrar conexión: {e}")
        
        # Obtener ruta de BD desde RW_Helisa para mayor precisión
        try:
            cfg = RW_Helisa('EX')
            path_bd = f"{cfg.bd}\\HELI{str(codigo).zfill(2)}BD.EXG"
        except Exception as e:
            print(f"[RESTAURAR] Error obteniendo ruta de BD: {e}")
            # Fallback a ruta hardcodeada
            path_bd = f"C:\\PROAsistemas\\EXOGENA\\{PERIODO}\\heli{str(codigo).zfill(2)}bd.exg"
        
        # Eliminar BD
        try:
            if os.path.exists(path_bd):
                os.remove(path_bd)
                print(f"[RESTAURAR] BD eliminada correctamente: {path_bd}")
            else:
                print(f"[RESTAURAR] La BD no existe en: {path_bd}, continuando...")
        except Exception as e:
            print(f"[RESTAURAR] Error eliminando BD: {e}")
            return e
        
        # Recrear BD
        try:
            crearBD_Particular(codigo, producto, loader, page)
            print(f"[RESTAURAR] BD recreada exitosamente")
            return None
        except Exception as e:
            print(f"[RESTAURAR] Error recreando BD: {e}")
            return e


def actualizar_activo(
    tabla: str,
    colactivo: str,
    colid: str,
    id_valor: Any,
    value: bool,
    codEmpresa: int,
) -> bool:
    """UPDATE tabla SET colactivo S/N donde colid = id_valor; tablas permitidas contra inyección."""
    try:
        tablas_permiso_activo = {
            "EMPRESAS",
            "USUARIOS",
            # Tablas BD particular
            "CUENTAS_TRIB",
            "CUENTAS_CONT",
            "CUENTAS_ATRIBUTOS",
            "TERCEROS",
            "CONSORCIOS",
            "CONCEPTOS",
            "FORMATOS",
            "ELEMENTOS",
            "ATRIBUTOS",
            "ACUMULADOS",
            "BANCOS_MOV",
            "FORMAACUMULADO",
            "HOJA_TRABAJO",
            "PRODUCTOS",
            "TERCEROS_MOV_CONT",
            "TERCEROS_MOV_TRIB",
        }
        tabla_normalizada = tabla.upper()
        if tabla_normalizada not in tablas_permiso_activo:
            print(f"Error: Tabla '{tabla}' no permitida para actualizar_activo")
            return False
        if not (colactivo.replace("_", "").isalnum() and colid.replace("_", "").isalnum()):
            print(f"Error: Nombres de columnas inválidos")
            return False
        valor_sn = "S" if value else "N"
        with transaccion_segura(codigo_empresa=codEmpresa) as (_con, cur):
            cur.execute(
                f"""
                UPDATE {tabla_normalizada}
                SET {colactivo} = ?
                WHERE {colid} = ?
                """,
                (valor_sn, id_valor),
            )
        return True
    except Exception as exc:
        print(f"Error actualizando activo en {tabla}: {exc}")
        return False
