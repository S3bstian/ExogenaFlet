"""Carga inicial de catálogos maestros en los dicts globales de `core.catalogues`."""

from application.ports.catalogos_maestros_ports import CatalogosMaestrosPort


class CargarCatalogosMaestrosUseCase:
    """Rellena PAISES, DEPARTAMENTOS, MUNICIPIOS y TIPOSDOC desde BD global."""

    def __init__(self, port: CatalogosMaestrosPort) -> None:
        self._port = port

    def ejecutar(self) -> str:
        import core.catalogues as catalogues

        try:
            self._port.asegurar_bd_global()
            paisesp = self._port.obtener_filas_traduccion("pais")
            parsed = catalogues._parse_paises(paisesp)
            if not parsed:
                parsed = catalogues._parse_paises(self._port.obtener_filas_traduccion("pais", "NI", -1))
            if not parsed:
                parsed = catalogues._FALLBACK_PAISES.copy()
            catalogues.PAISES.clear()
            catalogues.PAISES.update(parsed)

            departamentosp = self._port.obtener_filas_traduccion("departamento")
            parsed = catalogues._parse_departamentos(departamentosp)
            if not parsed:
                parsed = catalogues._parse_departamentos(
                    self._port.obtener_filas_traduccion("departamento", "NI", -1)
                )
            if not parsed:
                parsed = catalogues._FALLBACK_DEPARTAMENTOS.copy()
            catalogues.DEPARTAMENTOS.clear()
            catalogues.DEPARTAMENTOS.update(parsed)

            municipiosp = self._port.obtener_filas_traduccion("municipio")
            parsed = catalogues._parse_municipios(municipiosp)
            if not parsed:
                parsed = catalogues._parse_municipios(
                    self._port.obtener_filas_traduccion("municipio", "NI", -1)
                )
            if not parsed:
                parsed = catalogues._FALLBACK_MUNICIPIOS.copy()
            catalogues.MUNICIPIOS.clear()
            catalogues.MUNICIPIOS.update(parsed)

            tiposdocumentosp = self._port.obtener_filas_traduccion("tiposdocumentos")
            if tiposdocumentosp:
                try:
                    catalogues.TIPOSDOC.clear()
                    catalogues.TIPOSDOC.update(
                        {
                            codigo: [tipo, descripcion]
                            for codigo, tipo, descripcion in tiposdocumentosp
                        }
                    )
                except (ValueError, TypeError):
                    pass
            else:
                catalogues.TIPOSDOC.clear()
            return "✅ Validación completada con éxito"
        except Exception as e:
            return f"❌ Error: {e}"
