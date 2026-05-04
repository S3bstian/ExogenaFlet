"""Caso de uso para consulta paginada de conceptos."""

from typing import List, Optional, Tuple

from application.ports.toma_informacion_ports import ConceptosPort
from domain.entities.concepto_toma_informacion import ConceptoTomaInformacion


class ObtenerConceptosTomaInfoUseCase:
    """Orquesta la lectura de conceptos y valida parámetros mínimos."""

    def __init__(self, conceptos_port: ConceptosPort) -> None:
        self._conceptos_port = conceptos_port

    def ejecutar(
        self,
        *,
        offset: int,
        limit: int,
        filtro: Optional[str] = None,
    ) -> Tuple[List[ConceptoTomaInformacion], int]:
        if offset < 0 or limit < 0:
            raise ValueError("offset y limit deben ser valores no negativos")
        conceptos, total = self._conceptos_port.obtener_conceptos(
            offset=offset,
            limit=limit,
            filtro=filtro,
        )
        return conceptos, total
