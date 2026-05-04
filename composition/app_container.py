"""
Inyección de dependencias central (único lugar que instancia repos Firebird + casos de uso).

Reglas de capas (resumen): `paginas` solo usa este contenedor y UC; `application` solo
puertos y dominio; `infrastructure` implementa puertos y persistencia Firebird.
Ver `docs/ARQUITECTURA.md`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from application.use_cases.auth_app.gestion_auth_app import GestionAuthAppUseCase
    from application.use_cases.cartilla_terceros.gestion_terceros_cartilla import (
        GestionTercerosCartillaUseCase,
    )
    from application.use_cases.catalogos.cargar_catalogos_maestros import (
        CargarCatalogosMaestrosUseCase,
    )
    from application.use_cases.consorcios_app.gestion_consorcios_app import (
        GestionConsorciosAppUseCase,
    )
    from application.use_cases.cuentas_movimientos.gestion_catalogo_cuentas import (
        GestionCatalogoCuentasUseCase,
    )
    from application.use_cases.datos_especificos.gestion_datos_especificos import (
        GestionDatosEspecificosUseCase,
    )
    from application.use_cases.empresas_app.gestion_empresas_app import GestionEmpresasAppUseCase
    from application.use_cases.formatos_conceptos.gestion_formatos_ui import (
        GestionFormatosUIUseCase,
    )
    from application.use_cases.generar_xml.gestion_generar_xml import GestionGenerarXmlUseCase
    from application.use_cases.helisa_sesion.gestion_helisa_sesion import GestionHelisaSesionUseCase
    from application.use_cases.hoja_trabajo.consultar_hoja_trabajo import (
        ConsultarHojaTrabajoUseCase,
    )
    from application.use_cases.hoja_trabajo.mutar_hoja_trabajo import MutarHojaTrabajoUseCase
    from application.use_cases.licenciamiento.gestion_licenciamiento import (
        GestionLicenciamientoUseCase,
    )
    from application.use_cases.toma_informacion.acumular_conceptos import (
        AcumularConceptosTomaInfoUseCase,
    )
    from application.use_cases.toma_informacion.obtener_conceptos import (
        ObtenerConceptosTomaInfoUseCase,
    )


class AppContainer:
    """
    Compone adaptadores Firebird y casos de uso una sola vez al arrancar la app.

    Cualquier nueva dependencia de negocio debe registrarse aquí (repo + UC), no en
    páginas ni en módulos de `application` importando repositorios concretos.
    """

    def __init__(self) -> None:
        from application.use_cases.auth_app.gestion_auth_app import GestionAuthAppUseCase
        from application.use_cases.cartilla_terceros.gestion_terceros_cartilla import (
            GestionTercerosCartillaUseCase,
        )
        from application.use_cases.catalogos.cargar_catalogos_maestros import (
            CargarCatalogosMaestrosUseCase,
        )
        from application.use_cases.consorcios_app.gestion_consorcios_app import (
            GestionConsorciosAppUseCase,
        )
        from application.use_cases.cuentas_movimientos.gestion_catalogo_cuentas import (
            GestionCatalogoCuentasUseCase,
        )
        from application.use_cases.datos_especificos.gestion_datos_especificos import (
            GestionDatosEspecificosUseCase,
        )
        from application.use_cases.empresas_app.gestion_empresas_app import GestionEmpresasAppUseCase
        from application.use_cases.formatos_conceptos.gestion_formatos_ui import (
            GestionFormatosUIUseCase,
        )
        from application.use_cases.generar_xml.gestion_generar_xml import GestionGenerarXmlUseCase
        from application.use_cases.helisa_sesion.gestion_helisa_sesion import GestionHelisaSesionUseCase
        from application.use_cases.hoja_trabajo.consultar_hoja_trabajo import (
            ConsultarHojaTrabajoUseCase,
        )
        from application.use_cases.hoja_trabajo.mutar_hoja_trabajo import MutarHojaTrabajoUseCase
        from application.use_cases.licenciamiento.gestion_licenciamiento import (
            GestionLicenciamientoUseCase,
        )
        from application.use_cases.toma_informacion.acumular_conceptos import (
            AcumularConceptosTomaInfoUseCase,
        )
        from application.use_cases.toma_informacion.obtener_conceptos import (
            ObtenerConceptosTomaInfoUseCase,
        )
        from infrastructure.repositories.firebird.auth_app_repository import FirebirdAuthAppRepository
        from infrastructure.repositories.firebird.catalogos_maestros_repository import (
            FirebirdCatalogosMaestrosRepository,
        )
        from infrastructure.repositories.firebird.consorcios_app_repository import (
            FirebirdConsorciosAppRepository,
        )
        from infrastructure.repositories.firebird.cuentas_movimientos_repository import (
            FirebirdCuentasMovimientosRepository,
        )
        from infrastructure.repositories.firebird.datos_especificos_repository import (
            FirebirdDatosEspecificosRepository,
        )
        from infrastructure.repositories.firebird.empresas_app_repository import (
            FirebirdEmpresasAppRepository,
        )
        from infrastructure.repositories.firebird.formatos_conceptos_ui_repository import (
            FirebirdFormatosConceptosUIRepository,
        )
        from infrastructure.repositories.firebird.generar_xml_repository import (
            FirebirdGenerarXmlRepository,
        )
        from infrastructure.repositories.firebird.helisa_sesion_repository import (
            FirebirdHelisaSesionRepository,
        )
        from infrastructure.repositories.firebird.hoja_trabajo_repository import (
            FirebirdHojaTrabajoRepository,
        )
        from infrastructure.repositories.licenciamiento_repository import (
            WindowsLicenciamientoRepository,
        )
        from infrastructure.repositories.firebird.terceros_cartilla_repository import (
            FirebirdTercerosCartillaRepository,
        )
        from infrastructure.repositories.firebird.toma_informacion_repository import (
            FirebirdTomaInformacionRepository,
        )

        auth_repo = FirebirdAuthAppRepository()
        self.auth_uc: GestionAuthAppUseCase = GestionAuthAppUseCase(auth_repo)

        empresas_repo = FirebirdEmpresasAppRepository()
        self.empresas_uc: GestionEmpresasAppUseCase = GestionEmpresasAppUseCase(empresas_repo)

        helisa_repo = FirebirdHelisaSesionRepository()
        self.helisa_uc: GestionHelisaSesionUseCase = GestionHelisaSesionUseCase(helisa_repo)

        licenciamiento_repo = WindowsLicenciamientoRepository()
        self.licenciamiento_uc: GestionLicenciamientoUseCase = GestionLicenciamientoUseCase(
            licenciamiento_repo
        )

        self.consorcios_uc: GestionConsorciosAppUseCase = GestionConsorciosAppUseCase(
            FirebirdConsorciosAppRepository()
        )

        terceros_repo = FirebirdTercerosCartillaRepository()
        self.terceros_cartilla_uc: GestionTercerosCartillaUseCase = GestionTercerosCartillaUseCase(
            terceros_repo
        )

        self._formatos_ui_repo = FirebirdFormatosConceptosUIRepository()
        self.formatos_uc: GestionFormatosUIUseCase = GestionFormatosUIUseCase(
            self._formatos_ui_repo
        )

        hoja_repo = FirebirdHojaTrabajoRepository()
        self.consultar_hoja_uc: ConsultarHojaTrabajoUseCase = ConsultarHojaTrabajoUseCase(
            hoja_repo
        )
        self.mutar_hoja_uc: MutarHojaTrabajoUseCase = MutarHojaTrabajoUseCase(hoja_repo)

        toma_repo = FirebirdTomaInformacionRepository()
        self.obtener_conceptos_toma_uc: ObtenerConceptosTomaInfoUseCase = (
            ObtenerConceptosTomaInfoUseCase(toma_repo)
        )
        self.acumular_conceptos_toma_uc: AcumularConceptosTomaInfoUseCase = (
            AcumularConceptosTomaInfoUseCase(toma_repo)
        )

        generar_xml_repo = FirebirdGenerarXmlRepository()
        self.generar_xml_uc: GestionGenerarXmlUseCase = GestionGenerarXmlUseCase(generar_xml_repo)

        cuentas_repo = FirebirdCuentasMovimientosRepository()
        self.cuentas_uc: GestionCatalogoCuentasUseCase = GestionCatalogoCuentasUseCase(
            cuentas_repo
        )

        datos_repo = FirebirdDatosEspecificosRepository()
        self.datos_especificos_uc: GestionDatosEspecificosUseCase = GestionDatosEspecificosUseCase(
            datos_repo
        )

        catalogos_repo = FirebirdCatalogosMaestrosRepository()
        self.cargar_catalogos_uc: CargarCatalogosMaestrosUseCase = CargarCatalogosMaestrosUseCase(
            catalogos_repo
        )
