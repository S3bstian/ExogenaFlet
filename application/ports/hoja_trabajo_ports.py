"""Puertos de aplicación para el módulo Hoja de Trabajo."""

from typing import Any, Dict, List, Optional, Protocol, Tuple, TypeAlias, Union
from domain.entities.concepto_hoja_trabajo import ConceptoHojaTrabajo

ConceptoRef = Union[ConceptoHojaTrabajo, Dict[str, str], str]
FilaHoja: TypeAlias = Dict[str, Any]
FilasHojaMap: TypeAlias = Dict[str, FilaHoja]
ResultadoHojaPaginada: TypeAlias = Tuple[FilasHojaMap, bool, int]
ConceptoLegacyMap: TypeAlias = Dict[str, str]
EntradaHojaPayload: TypeAlias = Dict[str, Any]


class HojaTrabajoConsultaPort(Protocol):
    """Define contratos de lectura requeridos por Hoja de Trabajo."""

    def obtener_hoja_trabajo(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        concepto: Optional[Union[ConceptoRef, int]] = None,
        filtro: Optional[str] = None,
        solo_conceptos: bool = False,
    ) -> Union[List[ConceptoLegacyMap], ResultadoHojaPaginada]:
        """Consulta conceptos o filas de hoja según modo solicitado."""

    def obtener_conceptos(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        filtro: Optional[str] = None,
    ) -> Tuple[List[ConceptoLegacyMap], int]:
        """Consulta conceptos de la tabla de conceptos."""

class HojaTrabajoMutacionPort(Protocol):
    """Contratos de escritura y herramientas sobre la hoja (delegación a infraestructura)."""

    def eliminar_grupo_filas_hoja(
        self, id_concepto: int, identidad: str
    ) -> Union[bool, Exception]:
        """Elimina el registro de la hoja para (id_concepto, identidad)."""

    def unificar_grupos_hoja_trabajo(
        self,
        concepto: ConceptoRef,
        claves: List[str],
    ) -> Union[bool, str, Exception]:
        """Unifica filas seleccionadas en la primera identidad."""

    def obtener_identidades_a_agrupar_cuantias(
        self, concepto: ConceptoRef
    ) -> List[str]:
        """Lista identidades candidatas a agrupación de cuantías menores."""

    def agrupar_cuantias_menores(
        self, concepto: ConceptoRef
    ) -> Union[bool, str]:
        """Ejecuta agrupación de cuantías menores."""

    def deshacer_agrupar_cuantias(self, concepto: ConceptoRef) -> str:
        """Revierte agrupaciones de cuantías del concepto."""

    def obtener_terceros_a_numerar(
        self, concepto: ConceptoRef
    ) -> List[str]:
        """Terceros candidatos a numeración de NIT extranjero."""

    def numerar_nits_extranjeros(
        self, concepto: ConceptoRef
    ) -> str:
        """Ejecuta numeración de NITs extranjeros."""

    def deshacer_numerar_nits(self, concepto: ConceptoRef) -> str:
        """Revierte numeración de NITs del concepto."""

    def deshacer_unificar(self, concepto: ConceptoRef) -> str:
        """Revierte unificaciones del concepto."""

    def crear_entrada_hoja_trabajo(self, datos: EntradaHojaPayload) -> bool:
        """Inserta un nuevo registro completo en hoja."""

    def actualizar_entrada_hoja_trabajo(
        self, id_concepto: int, identidad: str, datos: EntradaHojaPayload
    ) -> bool:
        """Actualiza valores de atributos para una fila."""

    def eliminar_hoja_por_identidad(
        self,
        identidad: str,
        filtro: Optional[float] = None,
        campo_id: Optional[int] = None,
    ) -> Optional[Exception]:
        """Elimina filas por identidad y filtro opcional."""

    def eliminar_hoja_por_concepto(
        self,
        concepto: ConceptoRef,
        filtro: Optional[float] = None,
        campo_id: Optional[int] = None,
    ) -> Optional[Exception]:
        """Elimina filas por concepto y filtro opcional."""

    def obtener_valores_fideicomiso_existentes(
        self, concepto: ConceptoRef
    ) -> Dict[str, List[str]]:
        """Valores ya guardados para tipo/subtipo fideicomiso."""

    def actualizar_fideicomiso_masivo(
        self,
        concepto: ConceptoRef,
        tipo_fideicomiso: str,
        subtipo_fideicomiso: str,
        filtro_tipo_actual: str = "",
        filtro_subtipo_actual: str = "",
    ) -> str:
        """Actualización masiva tipo/subtipo fideicomiso."""
