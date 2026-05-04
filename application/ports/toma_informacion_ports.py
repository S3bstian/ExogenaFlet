"""Contratos para aislar casos de uso de la infraestructura."""

from typing import Any, Dict, List, Optional, Protocol, Tuple, TypeAlias, Union
from threading import Event
from domain.entities.concepto_toma_informacion import ConceptoTomaInformacion
from domain.entities.resultado_acumulacion import ResultadoAcumulacion

ConceptoTomaPayload: TypeAlias = Dict[str, Any]
ConceptoTomaRef = Union[ConceptoTomaInformacion, ConceptoTomaPayload]


class ConceptosPort(Protocol):
    """Define cómo obtener conceptos para la pantalla de toma de información."""

    def obtener_conceptos(
        self,
        *,
        offset: int,
        limit: int,
        filtro: Optional[str] = None,
    ) -> Tuple[List[ConceptoTomaInformacion], int]:
        """Retorna lista paginada de conceptos y total disponible."""


class AcumulacionConceptosPort(Protocol):
    """Define cómo ejecutar la acumulación de conceptos en hoja de trabajo."""

    def acumular_conceptos(
        self,
        *,
        conceptos: List[ConceptoTomaRef],
        loader: Any,
        page: Any,
        bottom_text: Any,
        cancel_event: Optional[Event] = None,
    ) -> ResultadoAcumulacion:
        """Ejecuta acumulación y retorna resultado detallado para la UI."""
