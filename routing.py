import flet as ft
from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple

from paginas.home import HomePage
from paginas.modulopasos.cartilla_terceros.cartillla_terceros import CartillaTercerosPage
from paginas.modulopasos.formatos_conceptos.formatos import FormatosPage
from paginas.modulopasos.generar_xml.generar_xml import GenerarXmlPage
from paginas.modulopasos.hoja_trabajo.hoja_trabajo import HojaTrabajoPage
from paginas.modulopasos.toma_informacion.toma_informacion import TomaInformacionPage
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO_SIN
from utils.paths import IMG_PATH

APPBAR_LOGIN = "login"
APPBAR_HOME = "home"

@dataclass
class RouteHandler:
    appbar: str
    build_view: Callable[[ft.Page, Any], Tuple[ft.Control, Optional[Any]]]
    on_enter: Optional[Callable[[ft.Page, Any], None]] = None


def _build_page(page_cls: type, page: ft.Page, app: Any) -> Tuple[ft.Control, Any]:
    """Construye una página por clase y retorna su vista junto con la instancia."""
    page_instance = page_cls(page, app)
    return page_instance.view(), page_instance


def _build_login(_page: ft.Page, app: Any) -> Tuple[ft.Control, None]:
    return (app.msg, None)


def _build_home(page: ft.Page, app: Any) -> Tuple[ft.Control, Any]:
    return _build_page(HomePage, page, app)


def _build_formatos(page: ft.Page, app: Any) -> Tuple[ft.Control, Any]:
    return _build_page(FormatosPage, page, app)


def _build_toma_informacion(page: ft.Page, app: Any) -> Tuple[ft.Control, Any]:
    return _build_page(TomaInformacionPage, page, app)


def _build_cartilla(page: ft.Page, app: Any) -> Tuple[ft.Control, Any]:
    return _build_page(CartillaTercerosPage, page, app)


def _build_hoja(page: ft.Page, app: Any) -> Tuple[ft.Control, Any]:
    return _build_page(HojaTrabajoPage, page, app)


def _build_generar_xml(page: ft.Page, app: Any) -> Tuple[ft.Control, Any]:
    return _build_page(GenerarXmlPage, page, app)


def _configurar_teclado_pagina(page: ft.Page, view_instance: Any) -> None:
    """Asigna el handler global de teclado cuando la vista lo requiere."""
    page.on_keyboard_event = view_instance._on_keyboard_page


def _on_enter_cartilla(page: ft.Page, vi: Any) -> None:
    _configurar_teclado_pagina(page, vi)
    vi.cargar_terceros()


def _on_enter_hoja(page: ft.Page, vi: Any) -> None:
    # Flet: un solo handler global; en esta ruta la hoja captura atajos de teclado.
    _configurar_teclado_pagina(page, vi)
    vi.cargar_conceptos()
    vi.cargar_datos()


def _on_enter_toma(page: ft.Page, vi: Any) -> None:
    _configurar_teclado_pagina(page, vi)


def _on_enter_formatos(_page: ft.Page, vi: Any) -> None:
    vi.actualizar_formatos()


def _on_enter_generar(_page: ft.Page, vi: Any) -> None:
    vi._cargar_formatos_y_abrir_dialogo()


def _on_enter_home(_page: ft.Page, vi: Any) -> None:
    vi._aplicar_carga_empresas()


# Orden: más específico primero para el match
RUTAS: list[Tuple[str, RouteHandler]] = [
    ("/home/generar_xml", RouteHandler(APPBAR_HOME, _build_generar_xml, _on_enter_generar)),
    ("/home/hoja_trabajo", RouteHandler(APPBAR_HOME, _build_hoja, _on_enter_hoja)),
    ("/home/cartilla_terceros", RouteHandler(APPBAR_HOME, _build_cartilla, _on_enter_cartilla)),
    ("/home/toma_informacion", RouteHandler(APPBAR_HOME, _build_toma_informacion, _on_enter_toma)),
    ("/home/formatos_conceptos", RouteHandler(APPBAR_HOME, _build_formatos, _on_enter_formatos)),
    ("/home", RouteHandler(APPBAR_HOME, _build_home, _on_enter_home)),
    ("/", RouteHandler(APPBAR_LOGIN, _build_login, None)),
]


def resolve_route(troute: ft.TemplateRoute) -> Optional[Tuple[str, RouteHandler]]:
    for ruta_registrada, manejador in RUTAS:
        if troute.match(ruta_registrada):
            return (ruta_registrada, manejador)
    return None


def parent_route_for_back(route: str) -> Optional[str]:
    """Ruta padre al usar Atrás: solo las pantallas bajo /home/... vuelven a /home."""
    if route.startswith("/home/"):
        return "/home"
    return None


def get_appbar_content(appbar_key: str, app: Any) -> Tuple[int, ft.Control]:
    if appbar_key == APPBAR_LOGIN:
        return (666, ft.Column(
            [
                ft.Row(
                    controls=[
                        app.logo_helisa,
                        ft.Container(expand=True),
                        app.backbutton,
                        app.login_button,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        ))

    return (
        55,
        ft.Stack(
            expand=True,
            height=130,
            clip_behavior=ft.ClipBehavior.NONE,
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(width=75),
                        ft.Container(
                            content=app._outer_banner_prefijo_appbar,
                            expand=True,
                            alignment=ft.Alignment.CENTER,
                        ),
                        app.backbutton,
                        app.login_button,
                    ],
                    expand=True,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Image(
                    src=IMG_PATH + "/helisa.png",
                    width=130,
                    height=75,
                    fit=ft.BoxFit.CONTAIN,
                    left=0,
                    top=(55 - 75) / 2
                ),
            ],
        ),
    )


def update_topbar(troute: ft.TemplateRoute, app: Any) -> None:
    esta_en_login = troute.match("/")
    esta_en_home = troute.match("/home")
    app.backbutton.visible = not (esta_en_login or esta_en_home)
    app.login_button.visible = esta_en_login or esta_en_home
    if esta_en_login:
        app.login_button.content = "Iniciar Sesión"
        app.login_button.icon = None
        app.login_button.style = BOTON_PRINCIPAL
        app.login_button.on_click = app.login
    elif esta_en_home:
        app.login_button.content = "Herramientas"
        app.login_button.icon = ft.Icons.SETTINGS
        app.login_button.style = BOTON_SECUNDARIO_SIN
        app.login_button.on_click = lambda _: app.herramientas_dialog.open_dialog()
