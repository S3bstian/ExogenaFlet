"""Adaptador Firebird/archivos XSD para Generar XML."""

from typing import List, Optional
from application.ports.generar_xml_ports import (
    AtributosXsdMap,
    CabeceraFormato,
    DatosIdentidadRow,
    FormatoRow,
    HojaParaXml,
    XmlGeneradoItem,
)

from infrastructure.persistence.firebird.formatos_persistencia import (
    consultar_formatos,
    persistir_cambios_formato,
)
from infrastructure.persistence.firebird.xml_xsd_persistencia import (
    _obtener_datos_identidad,
    generar_xml_formato,
    obtener_elemento_detalle_xsd,
    obtener_hoja_para_generar,
    obtener_orden_atributos_xsd,
    parsear_xsd,
    validar_formato_xsd,
)


class FirebirdGenerarXmlRepository:
    """Formatos vía ``formatos_persistencia``; XML/XSD vía ``xml_xsd_persistencia``."""

    def obtener_formatos(self) -> List[FormatoRow]:
        return consultar_formatos()

    def actualizar_formato(self, campos: CabeceraFormato, formato: str) -> bool:
        return persistir_cambios_formato(campos, formato)

    def parsear_xsd(self, formato_codigo: str) -> AtributosXsdMap:
        return parsear_xsd(formato_codigo)

    def obtener_orden_atributos_xsd(self, formato_codigo: str) -> List[str]:
        return obtener_orden_atributos_xsd(formato_codigo)

    def obtener_elemento_detalle_xsd(self, formato_codigo: str) -> Optional[str]:
        return obtener_elemento_detalle_xsd(formato_codigo)

    def obtener_datos_identidad(self, formato_codigo: str) -> List[DatosIdentidadRow]:
        return _obtener_datos_identidad(formato_codigo)

    def validar_formato_xsd(
        self,
        formato_codigo: str,
        atributos_xsd: Optional[AtributosXsdMap] = None,
        rows: Optional[List[DatosIdentidadRow]] = None,
    ) -> AtributosXsdMap:
        return validar_formato_xsd(
            formato_codigo,
            atributos_xsd=atributos_xsd,
            rows=rows,
        )

    def obtener_hoja_para_generar(
        self,
        formato_codigo: str,
        rows: Optional[List[DatosIdentidadRow]] = None,
    ) -> HojaParaXml:
        return obtener_hoja_para_generar(formato_codigo, rows=rows)

    def generar_xml_formato(
        self,
        formato_codigo: str,
        datos_cabecera: CabeceraFormato,
        orden_atributos: Optional[List[str]] = None,
        elemento_detalle: Optional[str] = None,
        datos_hoja: Optional[HojaParaXml] = None,
    ) -> List[XmlGeneradoItem]:
        return generar_xml_formato(
            formato_codigo,
            datos_cabecera,
            orden_atributos=orden_atributos,
            elemento_detalle=elemento_detalle,
            datos_hoja=datos_hoja,
        )
