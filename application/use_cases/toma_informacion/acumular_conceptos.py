"""Caso de uso para acumulación de conceptos en hoja de trabajo."""

from threading import Event
from typing import Any, List, Optional

from application.ports.toma_informacion_ports import AcumulacionConceptosPort
from domain.entities.resultado_acumulacion import ResultadoAcumulacion
from application.use_cases.toma_informacion.validar_seleccion import (
    validar_conceptos_seleccionados,
)
from domain.entities.concepto_toma_informacion import ConceptoTomaInformacion


class AcumularConceptosTomaInfoUseCase:
    """Ejecuta validaciones de negocio y delega la acumulación a infraestructura."""

    def __init__(self, acumulacion_port: AcumulacionConceptosPort) -> None:
        self._acumulacion_port = acumulacion_port

    def ejecutar(
        self,
        *,
        conceptos: List[ConceptoTomaInformacion],
        loader: Any,
        page: Any,
        bottom_text: Any,
        cancel_event: Optional[Event] = None,
    ) -> ResultadoAcumulacion:
        validar_conceptos_seleccionados(conceptos)
        return self._acumulacion_port.acumular_conceptos(
            conceptos=conceptos,
            loader=loader,
            page=page,
            bottom_text=bottom_text,
            cancel_event=cancel_event,
        )
