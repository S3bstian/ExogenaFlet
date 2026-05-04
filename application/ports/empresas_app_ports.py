"""Puerto para empresas en BD central y listados por producto."""

from typing import Any, Dict, List, Optional, Protocol, TypeAlias

EmpresaResumen: TypeAlias = Dict[str, Any]
FichaEmpresa: TypeAlias = Dict[str, Any]
ListaEmpresas: TypeAlias = List[EmpresaResumen]


class EmpresasAppPort(Protocol):
    """Listado y ficha de empresa."""

    def obtener_empresas(self, producto: str) -> ListaEmpresas:
        ...

    def obtener_info_empresa(
        self,
        producto: str,
        codigo_empresa: int,
    ) -> Optional[FichaEmpresa]:
        ...

    def actualizar_info_empresa(
        self,
        identidad: str,
        direccion: Optional[str],
        codigo_ciudad: Optional[str],
        codigo_departamento: Optional[str],
        codigo_pais: Optional[str],
    ) -> bool:
        ...
