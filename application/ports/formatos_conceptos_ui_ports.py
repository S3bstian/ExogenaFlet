"""Puertos para la pantalla de formatos y estructura de conceptos."""

from typing import Any, Dict, List, Optional, Protocol, Tuple, TypeAlias, Union
from domain.entities.concepto_hoja_trabajo import ConceptoHojaTrabajo

ConceptoRef = Union[ConceptoHojaTrabajo, Dict[str, str], int, str]
FormatoUiRow: TypeAlias = Tuple[Any, ...]
ElementoUiRow: TypeAlias = Tuple[Any, ...]
AtributoUiRow: TypeAlias = Tuple[Any, ...]
ConceptoUiRecord: TypeAlias = Dict[str, Any]
ListaConceptosUi: TypeAlias = List[ConceptoUiRecord]
CuentaConfigRecord: TypeAlias = Dict[str, Any]
ListaCuentasConfig: TypeAlias = List[CuentaConfigRecord]
ConfigAtributoResultado: TypeAlias = Optional[Tuple[int, int, ListaCuentasConfig]]


class FormatosConceptosUIPort(Protocol):
    """Consultas y actualizaciones usadas por `FormatosPage` y flujo de estructura."""

    def obtener_formatos(self) -> List[FormatoUiRow]:
        """Lista de formatos para el menú principal."""

    def obtener_conceptos(
        self,
        offset: int = 0,
        limit: int = 20,
        filtro: Optional[str] = None,
    ) -> Tuple[ListaConceptosUi, int]:
        """Conceptos paginados (misma semántica que ``conceptos_persistencia``)."""

    def obtener_elementos(
        self,
        concepto: Optional[Union[int, str]] = None,
        formato: Optional[int] = None,
    ) -> List[ElementoUiRow]:
        """Filas de ELEMENTOS para armar el árbol de estructura."""

    def obtener_atributos(
        self,
        elemento_id: Optional[int] = None,
        filtro: Optional[str] = None,
    ) -> List[AtributoUiRow]:
        """Atributos de un elemento."""

    def actualizar_tipo_global(self, elem_id: int, nuevo_tipo: str) -> bool:
        """Cambia tipo global de acumulación del elemento."""

    def obtener_atributos_por_concepto(
        self,
        concepto: ConceptoRef,
    ) -> List[AtributoUiRow]:
        """Atributos asociados al concepto (hoja de trabajo, diálogo de opciones)."""

    def obtener_forma_acumulado(
        self,
        codigo_empresa: Optional[int] = None,
    ) -> List[ElementoUiRow]:
        """Tipos de acumulado para configurar un atributo."""

    def obtener_configuracion_atributo(
        self,
        idatributo: int,
    ) -> ConfigAtributoResultado:
        """Tipo acumulado, tipo contabilidad y cuentas vinculadas al atributo."""

    def guardar_configuracion_atributo(
        self,
        atributo: ConceptoUiRecord,
        acumulado: int,
        tcuenta: int,
        cuentas: ListaCuentasConfig,
    ) -> bool:
        """Persiste configuración de acumulación y cuentas del atributo."""
