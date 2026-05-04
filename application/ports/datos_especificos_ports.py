"""Puerto para catálogo y mantenimiento de datos específicos (tabla T)."""

from typing import Any, Dict, List, Optional, Protocol, TypeAlias

DatoEspecifico: TypeAlias = Dict[str, Any]
ListaDatosEspecificos: TypeAlias = List[DatoEspecifico]


class DatosEspecificosPort(Protocol):
    """Operaciones usadas por el diálogo de atributos clase 2 y hoja de trabajo."""

    def obtener_opciones_datos_especificos(
        self,
        tabla: str,
        padre_tabla: Optional[str] = None,
        padre_valor: Optional[Any] = None,
    ) -> ListaDatosEspecificos:
        ...

    def obtener_padres_subtipo(
        self,
        tabla: Optional[str] = None,
    ) -> ListaDatosEspecificos:
        ...

    def obtener_tabla_padre_para_catalogo_dependiente(
        self, tabla_hija: str
    ) -> Optional[str]:
        """TABLA del catálogo padre si `tabla_hija` está enlazada vía HIJOS; si no, None."""
        ...

    def obtener_opciones_datos_especificos_por_codigos(
        self,
        codigos: List[int],
    ) -> ListaDatosEspecificos:
        ...

    def actualizar_hijos_padre_subtipo(
        self,
        tabla: str,
        codigo_padre: int,
        hijos: List[int],
    ) -> bool:
        ...

    def crear_dato_especifico(
        self,
        tabla: str,
        descripcion: str,
        codigos_base: Optional[List[int]] = None,
    ) -> Optional[int]:
        ...

    def eliminar_dato_especifico(self, tabla: str, codigo: int) -> bool:
        ...
