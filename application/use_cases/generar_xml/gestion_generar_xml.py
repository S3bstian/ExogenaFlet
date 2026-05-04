"""Orquestación de validación XSD y generación de archivos XML."""

from typing import List, Optional

from application.ports.generar_xml_ports import (
    AtributosXsdMap,
    CabeceraFormato,
    DatosIdentidadRow,
    FormatoRow,
    GenerarXmlPort,
    HojaParaXml,
    XmlGeneradoItem,
)


class GestionGenerarXmlUseCase:
    """Expone operaciones del flujo Generar XML sin acoplar la UI a Firebird."""

    def __init__(self, port: GenerarXmlPort) -> None:
        self._port = port

    def obtener_formatos(self) -> List[FormatoRow]:
        return self._port.obtener_formatos()

    def actualizar_formato(self, campos: CabeceraFormato, formato: str) -> bool:
        return self._port.actualizar_formato(campos, formato)

    def parsear_xsd(self, formato_codigo: str) -> AtributosXsdMap:
        return self._port.parsear_xsd(formato_codigo)

    def obtener_orden_atributos_xsd(self, formato_codigo: str) -> List[str]:
        return self._port.obtener_orden_atributos_xsd(formato_codigo)

    def obtener_elemento_detalle_xsd(self, formato_codigo: str) -> Optional[str]:
        return self._port.obtener_elemento_detalle_xsd(formato_codigo)

    def obtener_datos_identidad(self, formato_codigo: str) -> List[DatosIdentidadRow]:
        return self._port.obtener_datos_identidad(formato_codigo)

    def validar_formato_xsd(
        self,
        formato_codigo: str,
        atributos_xsd: Optional[AtributosXsdMap] = None,
        rows: Optional[List[DatosIdentidadRow]] = None,
    ) -> AtributosXsdMap:
        return self._port.validar_formato_xsd(
            formato_codigo,
            atributos_xsd=atributos_xsd,
            rows=rows,
        )

    def obtener_hoja_para_generar(
        self,
        formato_codigo: str,
        rows: Optional[List[DatosIdentidadRow]] = None,
    ) -> HojaParaXml:
        return self._port.obtener_hoja_para_generar(formato_codigo, rows=rows)

    def generar_xml_formato(
        self,
        formato_codigo: str,
        datos_cabecera: CabeceraFormato,
        orden_atributos: Optional[List[str]] = None,
        elemento_detalle: Optional[str] = None,
        datos_hoja: Optional[HojaParaXml] = None,
    ) -> List[XmlGeneradoItem]:
        return self._port.generar_xml_formato(
            formato_codigo,
            datos_cabecera,
            orden_atributos=orden_atributos,
            elemento_detalle=elemento_detalle,
            datos_hoja=datos_hoja,
        )
