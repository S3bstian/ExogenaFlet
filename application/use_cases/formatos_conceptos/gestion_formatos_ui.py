"""Orquestación de la pantalla de formatos y estructura."""

from typing import List, Optional, Union

from application.ports.formatos_conceptos_ui_ports import (
    AtributoUiRow,
    ConfigAtributoResultado,
    ConceptoRef,
    ConceptoUiRecord,
    ElementoUiRow,
    FormatoUiRow,
    FormatosConceptosUIPort,
    ListaConceptosUi,
    ListaCuentasConfig,
)


class GestionFormatosUIUseCase:
    """Expone operaciones de la pantalla sin acoplar imports de infraestructura."""

    def __init__(self, port: FormatosConceptosUIPort) -> None:
        self._port = port

    def obtener_formatos(self) -> List[FormatoUiRow]:
        return self._port.obtener_formatos()

    def obtener_conceptos(
        self,
        offset: int = 0,
        limit: int = 20,
        filtro: Optional[str] = None,
    ) -> tuple[ListaConceptosUi, int]:
        return self._port.obtener_conceptos(
            offset=offset, limit=limit, filtro=filtro
        )

    def obtener_elementos(
        self,
        concepto: Optional[Union[int, str]] = None,
        formato: Optional[int] = None,
    ) -> List[ElementoUiRow]:
        return self._port.obtener_elementos(concepto=concepto, formato=formato)

    def obtener_atributos(
        self,
        elemento_id: Optional[int] = None,
        filtro: Optional[str] = None,
    ) -> List[AtributoUiRow]:
        return self._port.obtener_atributos(
            elemento_id=elemento_id, filtro=filtro
        )

    def actualizar_tipo_global(self, elem_id: int, nuevo_tipo: str) -> bool:
        return self._port.actualizar_tipo_global(elem_id, nuevo_tipo)

    def obtener_atributos_por_concepto(
        self,
        concepto: ConceptoRef,
    ) -> List[AtributoUiRow]:
        return self._port.obtener_atributos_por_concepto(concepto)

    def obtener_forma_acumulado(
        self,
        codigo_empresa: Optional[int] = None,
    ) -> List[ElementoUiRow]:
        return self._port.obtener_forma_acumulado(codigo_empresa)

    def obtener_configuracion_atributo(
        self,
        idatributo: int,
    ) -> ConfigAtributoResultado:
        return self._port.obtener_configuracion_atributo(idatributo)

    def guardar_configuracion_atributo(
        self,
        atributo: ConceptoUiRecord,
        acumulado: int,
        tcuenta: int,
        cuentas: ListaCuentasConfig,
    ) -> bool:
        return self._port.guardar_configuracion_atributo(
            atributo, acumulado, tcuenta, cuentas
        )
