"""Casos de uso de lectura para Hoja de Trabajo."""

from typing import List, Optional, Union

from application.ports.hoja_trabajo_ports import (
    ConceptoRef,
    HojaTrabajoConsultaPort,
    ResultadoHojaPaginada,
)
from domain.entities.concepto_detalle_hoja_trabajo import ConceptoDetalleHojaTrabajo
from domain.entities.concepto_hoja_trabajo import ConceptoHojaTrabajo


class ConsultarHojaTrabajoUseCase:
    """Orquesta consultas de hoja con validaciones mínimas de paginación."""

    def __init__(self, consulta_port: HojaTrabajoConsultaPort) -> None:
        self._consulta_port = consulta_port

    def obtener_filas(
        self,
        *,
        offset: int,
        limit: int,
        concepto: Optional[Union[ConceptoRef, int]] = None,
        filtro: Optional[str] = None,
    ) -> ResultadoHojaPaginada:
        if offset < 0 or limit < 0:
            raise ValueError("offset y limit deben ser valores no negativos")
        resultado = self._consulta_port.obtener_hoja_trabajo(
            offset=offset,
            limit=limit,
            concepto=concepto,
            filtro=filtro,
            solo_conceptos=False,
        )
        return resultado

    def obtener_conceptos_en_hoja(self) -> List[ConceptoHojaTrabajo]:
        resultado = self._consulta_port.obtener_hoja_trabajo(solo_conceptos=True) or []
        return [ConceptoHojaTrabajo.from_mapping(mapeado) for mapeado in resultado]

    def obtener_concepto_completo(
        self,
        *,
        codigo: str,
        formato: str,
        limit: int = 1000,
    ) -> Optional[ConceptoDetalleHojaTrabajo]:
        lista_conceptos, _ = self._consulta_port.obtener_conceptos(
            offset=0,
            limit=limit,
            filtro=codigo,
        )
        encontrado = next(
            (
                item
                for item in lista_conceptos
                if item.get("codigo") == codigo and item.get("formato") == formato
            ),
            None,
        )
        if not encontrado:
            return None
        return ConceptoDetalleHojaTrabajo.from_mapping(encontrado)

