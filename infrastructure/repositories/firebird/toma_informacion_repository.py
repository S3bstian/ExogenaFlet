"""Adaptador Firebird para el flujo Toma de Información."""

from threading import Event
from typing import Any, Dict, List, Optional, Tuple
from application.ports.toma_informacion_ports import ConceptoTomaRef
from domain.entities.concepto_toma_informacion import ConceptoTomaInformacion
from domain.entities.resultado_acumulacion import ResultadoAcumulacion

from infrastructure.persistence.firebird.conceptos_persistencia import consultar_conceptos_paginados
from infrastructure.repositories.firebird.acumulacion_hoja_trabajo import (
    acumular_conceptos_hoja_trabajo,
)


class FirebirdTomaInformacionRepository:
    """
    Implementación concreta del repositorio de Toma de Información.

    Listado de conceptos vía ``conceptos_persistencia``; acumulación vía módulo dedicado en infrastructure.
    """

    @staticmethod
    def _legacy_concepto(concepto: ConceptoTomaRef) -> Dict[str, Any]:
        """Normaliza entidad de dominio a dict para la persistencia."""
        if isinstance(concepto, ConceptoTomaInformacion):
            return concepto.as_dict()
        return dict(concepto)

    def obtener_conceptos(
        self,
        *,
        offset: int,
        limit: int,
        filtro: Optional[str] = None,
    ) -> Tuple[List[ConceptoTomaInformacion], int]:
        rows, total = consultar_conceptos_paginados(
            offset=offset,
            limit=limit,
            filtro=filtro,
        )
        return [ConceptoTomaInformacion.from_mapping(r) for r in rows], total

    def acumular_conceptos(
        self,
        *,
        conceptos: List[ConceptoTomaRef],
        loader: Any,
        page: Any,
        bottom_text: Any,
        cancel_event: Optional[Event] = None,
    ) -> ResultadoAcumulacion:
        return acumular_conceptos_hoja_trabajo(
            [self._legacy_concepto(c) for c in conceptos],
            loader,
            page,
            bottom_text,
            cancel_event=cancel_event,
        )
