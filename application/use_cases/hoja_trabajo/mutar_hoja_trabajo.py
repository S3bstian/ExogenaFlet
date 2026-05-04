"""Casos de uso de mutación y herramientas sobre la hoja de trabajo."""

from typing import Dict, List, Optional, Union

from application.ports.hoja_trabajo_ports import (
    ConceptoRef,
    EntradaHojaPayload,
    HojaTrabajoMutacionPort,
)


class MutarHojaTrabajoUseCase:
    """Orquesta operaciones de escritura; delega persistencia al puerto."""

    def __init__(self, mutacion_port: HojaTrabajoMutacionPort) -> None:
        self._port = mutacion_port

    def eliminar_grupo_filas_hoja(
        self, id_concepto: int, identidad: str
    ) -> Union[bool, Exception]:
        return self._port.eliminar_grupo_filas_hoja(id_concepto, identidad)

    def unificar_grupos_hoja_trabajo(
        self,
        concepto: ConceptoRef,
        claves: List[str],
    ) -> Union[bool, str, Exception]:
        return self._port.unificar_grupos_hoja_trabajo(concepto, claves)

    def obtener_identidades_a_agrupar_cuantias(
        self, concepto: ConceptoRef
    ) -> List[str]:
        return self._port.obtener_identidades_a_agrupar_cuantias(concepto)

    def agrupar_cuantias_menores(
        self, concepto: ConceptoRef
    ) -> Union[bool, str]:
        return self._port.agrupar_cuantias_menores(concepto)

    def deshacer_agrupar_cuantias(self, concepto: ConceptoRef) -> str:
        return self._port.deshacer_agrupar_cuantias(concepto)

    def obtener_terceros_a_numerar(
        self, concepto: ConceptoRef
    ) -> List[str]:
        return self._port.obtener_terceros_a_numerar(concepto)

    def numerar_nits_extranjeros(
        self, concepto: ConceptoRef
    ) -> str:
        return self._port.numerar_nits_extranjeros(concepto)

    def deshacer_numerar_nits(self, concepto: ConceptoRef) -> str:
        return self._port.deshacer_numerar_nits(concepto)

    def deshacer_unificar(self, concepto: ConceptoRef) -> str:
        return self._port.deshacer_unificar(concepto)

    def crear_entrada_hoja_trabajo(self, datos: EntradaHojaPayload) -> bool:
        return self._port.crear_entrada_hoja_trabajo(datos)

    def actualizar_entrada_hoja_trabajo(
        self, id_concepto: int, identidad: str, datos: EntradaHojaPayload
    ) -> bool:
        return self._port.actualizar_entrada_hoja_trabajo(
            id_concepto, identidad, datos
        )

    def eliminar_hoja_por_identidad(
        self,
        identidad: str,
        filtro: Optional[float] = None,
        campo_id: Optional[int] = None,
    ) -> Optional[Exception]:
        return self._port.eliminar_hoja_por_identidad(
            identidad, filtro=filtro, campo_id=campo_id
        )

    def eliminar_hoja_por_concepto(
        self,
        concepto: ConceptoRef,
        filtro: Optional[float] = None,
        campo_id: Optional[int] = None,
    ) -> Optional[Exception]:
        return self._port.eliminar_hoja_por_concepto(
            concepto, filtro=filtro, campo_id=campo_id
        )

    def obtener_valores_fideicomiso_existentes(
        self, concepto: ConceptoRef
    ) -> Dict[str, List[str]]:
        return self._port.obtener_valores_fideicomiso_existentes(concepto)

    def actualizar_fideicomiso_masivo(
        self,
        concepto: ConceptoRef,
        tipo_fideicomiso: str,
        subtipo_fideicomiso: str,
        filtro_tipo_actual: str = "",
        filtro_subtipo_actual: str = "",
    ) -> str:
        return self._port.actualizar_fideicomiso_masivo(
            concepto,
            tipo_fideicomiso,
            subtipo_fideicomiso,
            filtro_tipo_actual=filtro_tipo_actual,
            filtro_subtipo_actual=filtro_subtipo_actual,
        )
