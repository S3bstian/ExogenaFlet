"""
Conexión Firebird/Helisa, registro de Windows y creación de bases (global/particular).

DDL: ``infrastructure.persistence.firebird.bd_constructor``.
La carga inicial se ejecuta aquí vía ``infrastructure.persistence.firebird`` tras crear el esquema.
"""
import os
import subprocess
import winreg

import firebirdsql
from core.settings import PERIODO


def clonar_bd(origen, destino, servidor="localhost", usuario="sysdba", password="masterkey"):
    # 1. Backup de la base origen
    gbak = r"C:\Program Files (x86)\Firebird\Firebird_3_0\gbak.exe"
    try:
        subprocess.run([
            gbak, "-g",
            f"{servidor}:{origen}",
            "temp_clone.fbk",
            "-user", usuario,
            "-pass", password
        ], check=True)

        # 2. Restore en la nueva ruta
        subprocess.run([
            gbak, "-c",
            "temp_clone.fbk",
            f"{servidor}:{destino}",
            "-user", usuario,
            "-pass", password,
            "-p", "4096"
        ], check=True)
        print("gbak exitoso")
    except subprocess.CalledProcessError as e:
        print("gbak falló")
        print("Código:", e.returncode)

def encriptarCadena(pCadena: str):
    """
        Retorna una cadena encriptada para la cadena del parametro
        pCadena: Cadena a encriptar
    """
    resultado = ""
    for indice in range(len(pCadena), 0, -1):
        caracter = pCadena[indice - 1]
        codigo = ord(caracter)
        if indice % 2 != 0:
            resultado += chr(codigo - indice)
        else:
            resultado += chr(codigo + indice)
    return resultado


def desencriptarCadena(pCadena: str):
    """
        Retorna una cadena desencriptado la cadena del parametro
        pCadena: Cadena a desencriptar
    """
    resultado = ""
    longitud = len(pCadena)
    for posicion_reversa in range(longitud, 0, -1):
        indice_ajuste = longitud - posicion_reversa + 1
        if indice_ajuste % 2 != 0:
            resultado += chr(ord(pCadena[posicion_reversa - 1]) + indice_ajuste)
        else:
            resultado += chr(ord(pCadena[posicion_reversa - 1]) - indice_ajuste)
    return resultado

def CNX_BDHelisa(producto: str, codigoEmpresa: int, usuario):
    """
    Retorna la conexión a las bases de datos de helisa.
    producto: 'NI' = Norma internacional, 'PH' = Propiedad Horizontal, 'EX' = Informacion Exogena.
    codigoEmpresa: -2 = Base de datos XX, -1 = Base de datos Global, 0 .. 99 = Base de datos de la empresa
    periodoGravable: El año en que se reporta.
    usuario: usuario de firebird con el que se debe hacer la conexion (HELISAADMON, SYSDBA, HELISAPUBLICO)
    """
    rw_helisa = RW_Helisa(producto)
    base_datos = ""
    match usuario:
        case "HELISAADMON":
            password_fb = chr(66) + chr(56) + chr(64) + chr(65) + chr(106) + chr(78) + chr(63) + chr(90)
        case "sysdba":
            password_fb = rw_helisa.fb
        case "HELISAPUBLICO":
            password_fb = "usuhelpu"

    match producto:
        case "NI":
            extension_bd = ".HGW"
        case "PH":
            extension_bd = ".HPH"
        case "EX":
            extension_bd = ".EXG"

    match codigoEmpresa:
        case -2:
            base_datos = rw_helisa.bd + r"\\HELISAXX" + extension_bd
        case -1:
            base_datos = rw_helisa.bd + r"\\HELISABD" + extension_bd
        case _:
            base_datos = rw_helisa.bd + r"\\HELI" + str(codigoEmpresa).zfill(2) + "BD" + extension_bd
    # Evitar saturar la consola: cada consulta abre conexión; depuración solo con EXOGENA_DEBUG_BD=1
    if os.environ.get("EXOGENA_DEBUG_BD", "").strip().lower() in ("1", "true", "yes"):
        print(f"producto:{producto}, codigo empresa: {codigoEmpresa}, usuario: {usuario}.")
    try:
        conexion = firebirdsql.connect(
            host=rw_helisa.servidor,
            database=base_datos,
            port=3050,
            user=usuario,
            password=password_fb,
            charset="ISO8859_1",
        )
        return conexion
    except Exception as exc:
        error_msg = f"Error inesperado al conectar a la base de datos: {str(exc)}"
        print(f"[ERROR BD] {error_msg}")
        return None
def RW_CrearLlaveExogena(servidor: str, bd: str, fb:str):
    """
    Crea en el registro de windows las claves de exógena con el nombre del servidor,
    la ruta de las bases de datos y la clave del sydba.
    producto: NI = norma internacional, PH = Propiedad Horizontal, EX = Exógena.
    periodoGravable: Año que se reporta.
    servidor: Nombre del servidor.
    bd: Ruta de la bd
    fb: clave del sysdba de firebir
    """

    print(f"entra a crearllaves-------")
    rwHelisaNI = RW_Helisa('NI')
    rwHelisaPH = RW_Helisa('PH')
    llaveReg = r"Software\\WOW6432Node\\Helisa\\Exogena\\" + str(PERIODO)
    key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, llaveReg)
    winreg.SetValueEx(key, "Servidor", 0, winreg.REG_SZ, servidor)
    winreg.SetValueEx(key, "Base de datos", 0, winreg.REG_SZ, bd)
    winreg.SetValueEx(key, "Sysdba", 0, winreg.REG_SZ, fb)
    winreg.CloseKey(key)
    print("se lleno ex")

    key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, llaveReg + '\\NI')
    winreg.SetValueEx(key, "Servidor", 0, winreg.REG_SZ, rwHelisaNI.servidor)
    winreg.SetValueEx(key, "Base de datos", 0, winreg.REG_SZ, rwHelisaNI.bd)
    winreg.SetValueEx(key, "Sysdba", 0, winreg.REG_SZ, fb)
    winreg.CloseKey(key)
    print("se lleno ni de ex")

    key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, llaveReg + '\\PH')
    winreg.SetValueEx(key, "Servidor", 0, winreg.REG_SZ, rwHelisaPH.servidor)
    winreg.SetValueEx(key, "Base de datos", 0, winreg.REG_SZ, rwHelisaPH.bd)
    winreg.SetValueEx(key, "Sysdba", 0, winreg.REG_SZ, fb)
    winreg.CloseKey(key)
    print("se lleno ph de ex")

def crearBD_Global():
    bd = CNX_BDHelisa('EX', -1, "sysdba")
    if not bd:
        print("------Se entra a crearbdglobal-------")
        cfg = RW_Helisa('EX')
        base = str(cfg.bd + "\\" + "HELISABD.EXG")
        cx = firebirdsql.create_database(host = cfg.servidor,
                                         database = base,
                                         port = 3050,
                                         user = "sysdba",
                                         password = "masterkey",
                                         charset = "ISO8859_1"
                                         )
        cx.close()
        print(" se creo la bdglobal")
        bd = CNX_BDHelisa('EX', -1, "sysdba")
        try:
            if bd:
                from infrastructure.persistence.firebird.bd_constructor import (
                    Dominios,
                    Empresas,
                    Usuarios,
                )
                from infrastructure.persistence.firebird.empresas_persistencia import (
                    poblar_empresas_desde_productos,
                )

                Dominios(bd)
                Usuarios(bd)
                Empresas(bd)
                poblar_empresas_desde_productos()
                print(" se entro y creo dominios en la bdglobal")
        except Exception as exc:
            print(f"no se insertaron las tablas {exc}")
    else:
        print("Ya habia bd global----------")

def crearBD_Particular(codigoEmpresa, producto, loader, page=None):
    import time
    from utils.ui_sync import actualizar_progreso_ui

    pasos = 0
    page = page or getattr(loader, "page", None)
    total_pasos = 11

    def _actualizar_loader():
        v = max(0.01, min(1.0, pasos / total_pasos))
        actualizar_progreso_ui(loader, valor=v, page=page)
        time.sleep(0.03)

    bd = CNX_BDHelisa('EX', codigoEmpresa, "sysdba")
    if not bd:
        print("------Se entra a crearbdparticular-------")
        cfg = RW_Helisa('EX')
        origen = f"C:\\Proasistemas\\Exogena\\{PERIODO}\\HELISAXX.EXG"
        destino = str(cfg.bd + r"\\HELI" + str(codigoEmpresa).zfill(2) + 'BD.EXG')
        clonar_bd(origen, destino, servidor=cfg.servidor)
        pasos += 1
        _actualizar_loader()
        print(f"Se creó la BD particular {codigoEmpresa} clonada desde la XX")
        bd = CNX_BDHelisa('EX', codigoEmpresa, "sysdba")
        try:
            from infrastructure.persistence.firebird.bd_constructor import (
                Bancos_mov,
                Consorcios,
                Cuentas_Atributos,
                Cuentas_cont,
                Cuentas_trib,
                Hoja_trabajo,
                Terceros,
                Terceros_mov_cont,
                Terceros_mov_trib,
            )
            from infrastructure.persistence.firebird.cuentas_movimientos_persistencia import (
                obtener_cuentas_producto,
                obtener_movimientos_bancos_producto,
                obtener_movimientos_terceros_producto,
            )
            from infrastructure.persistence.firebird.terceros_persistencia import (
                obtener_terceros_producto,
            )

            pasos += 1
            _actualizar_loader()
            Terceros(bd, codigoEmpresa, producto)
            print("cargando terceros ----------------")
            obtener_terceros_producto(codigoEmpresa, producto)
            print("fin terceros ----------------")
            pasos += 1
            _actualizar_loader()
            Consorcios(bd)
            pasos += 1
            _actualizar_loader()
            Cuentas_trib(bd, codigoEmpresa, producto)
            print("cargando cuentas trib ****************")
            obtener_cuentas_producto(1, codigoEmpresa, producto)
            print("fin cuentas trib **********")
            pasos += 1
            _actualizar_loader()
            Cuentas_cont(bd, codigoEmpresa, producto)
            print("cargando cuentas cont ****************")
            obtener_cuentas_producto(2, codigoEmpresa, producto)
            print("fin cuentas cont **********")
            pasos += 1
            _actualizar_loader()
            Terceros_mov_trib(bd, codigoEmpresa, producto)
            print("cargando terceros trib ****************")
            obtener_movimientos_terceros_producto(1, codigoEmpresa, producto)
            print("fin terceros trib **********")
            pasos += 1
            _actualizar_loader()
            Terceros_mov_cont(bd, codigoEmpresa, producto)
            print("cargando terceros cont ****************")
            obtener_movimientos_terceros_producto(2, codigoEmpresa, producto)
            print("fin terceros cont **********")
            pasos += 1
            Bancos_mov(bd, codigoEmpresa, producto)
            print("cargando bancos ****************")
            obtener_movimientos_bancos_producto(codigoEmpresa, producto)
            print("fin bancos **********")
            pasos += 1
            _actualizar_loader()
            Cuentas_Atributos(bd)
            pasos += 1
            _actualizar_loader()
            Hoja_trabajo(bd)
            pasos += 1
            _actualizar_loader()
            bd.close()
        except Exception as exc:
            print(f"no se insertaron las tablas {exc}")

    else:
        print("Ya habia bd particular----------", codigoEmpresa)

        actualizar_progreso_ui(loader, valor=1.0, page=page)
        time.sleep(0.3)
        bd.close()

class RW_Helisa:
    def __init__(self, producto: str):
        """
        Lee el registro de windows y retorna el nombre del servidor, la ruta de las bases de datos y la clave sysdba.
        producto: 'NI = Norma Internacional, PH = Propiedad Horizontal, EX = Exógena.
        periodoGravable: Año que se reporta.
        """
        print(f"entra a rw como {producto}--------")
        match producto:
            case 'EX':
                llaveReg = r"Software\\WOW6432Node\\Helisa\\Exogena\\" + str(PERIODO)
            case 'NI':
                llaveReg = r"Software\\WOW6432Node\\Helisa\\Software Administrativo y de Gestion 2"
            case 'PH':
                llaveReg = r"Software\\WOW6432Node\\Helisa\\Administración de propiedad horizontal"

        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, llaveReg) as key:
                self.servidor, tipo = winreg.QueryValueEx(key, 'Servidor')
                self.bd, tipo = winreg.QueryValueEx(key, 'Base de datos')
                self.fb, tipo = winreg.QueryValueEx(key, 'Sysdba')
                self.fb = desencriptarCadena(self.fb)
                self.existe = True
                print("se envio key")
        except Exception as exc:
            print(" no se abrio el key, se entra al inicializar", exc)
            self._inicializar()

    def _inicializar(self):
        """Inicializa valores por defecto cuando no se puede leer el registro de Windows."""
        self.servidor = "LocalHost"
        self.bd = r"C:\\Proasistemas\\Exogena\\"+ str(PERIODO)
        self.fb = encriptarCadena("masterkey")
        self.existe = False
