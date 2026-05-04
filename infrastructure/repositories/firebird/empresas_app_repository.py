"""Adaptador: empresas globales."""

from typing import Optional

from application.ports.empresas_app_ports import FichaEmpresa, ListaEmpresas
from infrastructure.persistence.firebird.empresas_persistencia import (
    actualizar_info_empresa,
    obtener_empresas,
    obtener_info_empresa,
)


class FirebirdEmpresasAppRepository:
    """Delega en `infrastructure.persistence.firebird.empresas_persistencia`."""

    def obtener_empresas(self, producto: str) -> ListaEmpresas:
        return obtener_empresas(producto)

    def obtener_info_empresa(
        self,
        producto: str,
        codigo_empresa: int,
    ) -> Optional[FichaEmpresa]:
        return obtener_info_empresa(producto, codigo_empresa)

    def actualizar_info_empresa(
        self,
        identidad: str,
        direccion: Optional[str],
        codigo_ciudad: Optional[str],
        codigo_departamento: Optional[str],
        codigo_pais: Optional[str],
    ) -> bool:
        return actualizar_info_empresa(
            identidad,
            direccion,
            codigo_ciudad,
            codigo_departamento,
            codigo_pais,
        )
