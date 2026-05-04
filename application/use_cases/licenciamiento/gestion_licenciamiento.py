"""Caso de uso de licenciamiento; la UI solo consume estos métodos."""

from typing import Optional

from application.ports.licenciamiento_ports import LicenciamientoPort
from domain.entities.licencia import Licencia


class GestionLicenciamientoUseCase:
    """Orquesta condiciones de uso, activación de clave y activación de empresas."""

    def __init__(self, port: LicenciamientoPort) -> None:
        self._port = port

    def obtener_licencia(self) -> Optional[Licencia]:
        return self._port.obtener_licencia()

    def condiciones_aceptadas(self) -> bool:
        return self._port.condiciones_aceptadas()

    def requiere_primera_ejecucion(self) -> bool:
        """True mientras no exista licencia completa (clave + cupo persistidos)."""
        return self._port.obtener_licencia() is None

    def aceptar_condiciones(self) -> None:
        self._port.aceptar_condiciones()

    def activar_licencia(self, clave: str) -> Optional[Licencia]:
        return self._port.activar_licencia(clave)

    def activar_empresa(self, producto: str, codigo_empresa: int) -> bool:
        return self._port.activar_empresa(producto, codigo_empresa)
