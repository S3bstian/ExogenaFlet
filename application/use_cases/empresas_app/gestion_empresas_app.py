"""Listado y edición de empresas para la UI."""

from typing import Optional

from application.ports.empresas_app_ports import (
    EmpresasAppPort,
    FichaEmpresa,
    ListaEmpresas,
)


class GestionEmpresasAppUseCase:
    """Expone empresas sin acoplar la UI a Firebird."""

    def __init__(self, port: EmpresasAppPort) -> None:
        self._port = port

    def obtener_empresas(self, producto: str) -> ListaEmpresas:
        return self._port.obtener_empresas(producto)

    def obtener_info_empresa(
        self,
        producto: str,
        codigo_empresa: int,
    ) -> Optional[FichaEmpresa]:
        return self._port.obtener_info_empresa(producto, codigo_empresa)

    def actualizar_info_empresa(
        self,
        identidad: str,
        direccion: Optional[str],
        codigo_ciudad: Optional[str],
        codigo_departamento: Optional[str],
        codigo_pais: Optional[str],
    ) -> bool:
        return self._port.actualizar_info_empresa(
            identidad,
            direccion,
            codigo_ciudad,
            codigo_departamento,
            codigo_pais,
        )
