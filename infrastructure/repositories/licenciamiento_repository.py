"""Adaptador de licenciamiento: registro de Windows + stubs del servicio online."""

from __future__ import annotations

from typing import List, Optional
import winreg

from application.ports.licenciamiento_ports import LicenciamientoPort
from core.settings import (
    LICENCIA_MOCK_CUPO_EMPRESAS,
    LICENCIA_MOCK_SIN_API,
    PERIODO,
)
from domain.entities.licencia import Licencia
from infrastructure.adapters.fn_bd_helisa import desencriptarCadena, encriptarCadena


# Requisito de negocio: solo HKLM (rama administrativa de Helisa/Exógena).
_LLAVE_HKLM = r"Software\WOW6432Node\Helisa\Exogena\{periodo}".format(periodo=PERIODO)

# Nombres de valores en el registro (algunos los escribe el instalador Inno Setup).
_VAL_PRODUCTO = "ProductoLicenciado"
_VAL_CLAVE = "ClaveActivacion"
_VAL_LIMITE = "LimiteEmpresas"
_VAL_EMPRESAS = "EmpresasActivadas"
_VAL_CONDICIONES = "CondicionesAceptadas"

# TODO: reemplazar URLs cuando exista el servicio real.
URL_SERVICIO_LICENCIA = "https://TODO/api/license/activate"
URL_SERVICIO_ACTIVACION_EMPRESA = "https://TODO/api/license/activate-company"



class WindowsLicenciamientoRepository:
    """Persiste estado de licencia en registro y delega validaciones al servicio."""

    def obtener_licencia(self) -> Optional[Licencia]:
        producto = self._leer_str(_VAL_PRODUCTO)
        clave_cifrada = self._leer_str(_VAL_CLAVE)
        limite_str = self._leer_str(_VAL_LIMITE)
        if not producto or not clave_cifrada or not limite_str:
            return None
        return Licencia(
            producto=producto,
            clave=desencriptarCadena(clave_cifrada),
            limite_empresas=int(limite_str),
            empresas_activadas=self._leer_empresas(),
            condiciones_aceptadas=(self._leer_str(_VAL_CONDICIONES) == "S"),
        )

    def condiciones_aceptadas(self) -> bool:
        return self._leer_str(_VAL_CONDICIONES) == "S"

    def aceptar_condiciones(self) -> None:
        self._escribir_str(_VAL_CONDICIONES, "S")

    def activar_licencia(self, clave: str) -> Optional[Licencia]:
        producto = self._leer_str(_VAL_PRODUCTO)
        if not producto and LICENCIA_MOCK_SIN_API:
            producto = "NI"
            self._escribir_str(_VAL_PRODUCTO, producto)
        elif not producto:
            return None

        if LICENCIA_MOCK_SIN_API:
            limite = max(1, int(LICENCIA_MOCK_CUPO_EMPRESAS))
            clave_guardar = (clave or "").strip() or "PENDIENTE-VALIDACION-HELISA"
        else:
            limite = self._validar_clave_online(producto, clave)
            if limite is None:
                return None
            clave_guardar = (clave or "").strip()
            if not clave_guardar:
                return None

        self._escribir_str(_VAL_CLAVE, encriptarCadena(clave_guardar))
        self._escribir_str(_VAL_LIMITE, str(limite))
        return Licencia(
            producto=producto,
            clave=clave_guardar,
            limite_empresas=limite,
            empresas_activadas=self._leer_empresas(),
            condiciones_aceptadas=(self._leer_str(_VAL_CONDICIONES) == "S"),
        )

    def activar_empresa(self, producto: str, codigo_empresa: int) -> bool:
        if not self._enviar_activacion_empresa(codigo_empresa):
            return False
        empresas = self._leer_empresas()
        clave = Licencia.clave_empresa(producto, codigo_empresa)
        if clave not in empresas:
            empresas.append(clave)
            self._escribir_str(_VAL_EMPRESAS, ",".join(empresas))
        return True

    # ------------------- Stubs del servicio online (reemplazar) -------------------

    @staticmethod
    def _validar_clave_online(producto: str, clave: str) -> Optional[int]:
        """STUB temporal hasta servicio real: con clave no vacía retorna el cupo configurado."""
        clave = (clave or "").strip()
        if not clave:
            return None
        return max(1, int(LICENCIA_MOCK_CUPO_EMPRESAS))

    @staticmethod
    def _enviar_activacion_empresa(codigo_empresa: int) -> bool:
        """STUB: hoy siempre acepta. Reemplazar por POST a URL_SERVICIO_ACTIVACION_EMPRESA."""
        return True

    # --------------------------- Helpers de registro ------------------------------

    @staticmethod
    def _leer_str_en_llave(hive: int, subkey: str, nombre: str) -> str:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                raw, _ = winreg.QueryValueEx(key, nombre)
                return str(raw) if raw is not None else ""
        except OSError:
            return ""

    def _leer_str(self, nombre: str) -> str:
        """Lectura exclusiva desde HKLM."""
        return self._leer_str_en_llave(winreg.HKEY_LOCAL_MACHINE, _LLAVE_HKLM, nombre)

    def _escribir_str(self, nombre: str, valor: str) -> None:
        """Escritura exclusiva en HKLM (requiere permisos de administrador)."""
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, _LLAVE_HKLM) as key:
            winreg.SetValueEx(key, nombre, 0, winreg.REG_SZ, valor)

    def _leer_empresas(self) -> List[str]:
        crudo = self._leer_str(_VAL_EMPRESAS)
        if not crudo:
            return []
        items = []
        for x in crudo.split(","):
            token = str(x).strip()
            if not token:
                continue
            if ":" in token:
                items.append(token.upper())
            elif token.isdigit():
                # Compatibilidad con instalaciones previas que guardaron solo código.
                items.append(Licencia.clave_empresa("NI", int(token)))
        return items
