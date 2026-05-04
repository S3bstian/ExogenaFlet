# Router por registro: RUTAS, get_appbar_content, update_topbar, parent_route_for_back.
# build_view(page, app) -> (content: ft.Control, view_instance | None)
# on_enter(page, view_instance) | None

import flet as ft
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO_SIN
from utils.paths import IMG_PATH
from dataclasses import dataclass
from typing import Callable, Optional, Any, Tuple

from paginas.home import HomePage
from paginas.modulopasos.toma_informacion.toma_informacion import TomaInformacionPage
from paginas.modulopasos.cartilla_terceros.cartillla_terceros import CartillaTercerosPage
from paginas.modulopasos.hoja_trabajo.hoja_trabajo import HojaTrabajoPage
from paginas.modulopasos.generar_xml.generar_xml import GenerarXmlPage
from paginas.modulopasos.formatos_conceptos.formatos import FormatosPage

@dataclass
class RouteHandler:
    appbar: str  # "login" | "home"
    build_view: Callable[[ft.Page, Any], Tuple[ft.Control, Optional[Any]]]
    on_enter: Optional[Callable[[ft.Page, Any], None]] = None


def _build_login(_page: ft.Page, app: Any) -> Tuple[ft.Control, None]:
    return (app.msg, None)


def _build_home(page: ft.Page, app: Any) -> Tuple[ft.Control, Any]:
    p = HomePage(page, app)
    return (p.view(), p)


def _build_formatos(page: ft.Page, app: Any) -> Tuple[ft.Control, Any]:
    p = FormatosPage(page, app)
    return (p.view(), p)


def _build_toma_informacion(page: ft.Page, app: Any) -> Tuple[ft.Control, Any]:
    p = TomaInformacionPage(page, app)
    return (p.view(), p)


def _build_cartilla(page: ft.Page, app: Any) -> Tuple[ft.Control, Any]:
    p = CartillaTercerosPage(page, app)
    return (p.view(), p)


def _build_hoja(page: ft.Page, app: Any) -> Tuple[ft.Control, Any]:
    p = HojaTrabajoPage(page, app)
    return (p.view(), p)


def _build_generar_xml(page: ft.Page, app: Any) -> Tuple[ft.Control, Any]:
    p = GenerarXmlPage(page, app)
    return (p.view(), p)


def _on_enter_cartilla(page: ft.Page, vi: Any) -> None:
    page.on_keyboard_event = vi._on_keyboard_page
    vi.cargar_terceros()


def _on_enter_hoja(page: ft.Page, vi: Any) -> None:
    # Flet: un solo handler global; en esta ruta la hoja captura atajos de teclado.
    page.on_keyboard_event = vi._on_keyboard_page
    vi.cargar_conceptos()
    vi.cargar_datos()


def _on_enter_toma(page: ft.Page, vi: Any) -> None:
    page.on_keyboard_event = vi._on_keyboard_page


def _on_enter_formatos(_page: ft.Page, vi: Any) -> None:
    vi.actualizar_formatos()


def _on_enter_generar(_page: ft.Page, vi: Any) -> None:
    vi._cargar_formatos_y_abrir_dialogo()


def _on_enter_home(_page: ft.Page, vi: Any) -> None:
    vi._aplicar_carga_empresas()


# Orden: más específico primero para el match
RUTAS: list[Tuple[str, RouteHandler]] = [
    ("/home/generar_xml", RouteHandler("home", _build_generar_xml, _on_enter_generar)),
    ("/home/hoja_trabajo", RouteHandler("home", _build_hoja, _on_enter_hoja)),
    ("/home/cartilla_terceros", RouteHandler("home", _build_cartilla, _on_enter_cartilla)),
    ("/home/toma_informacion", RouteHandler("home", _build_toma_informacion, _on_enter_toma)),
    ("/home/formatos_conceptos", RouteHandler("home", _build_formatos, _on_enter_formatos)),
    ("/home", RouteHandler("home", _build_home, _on_enter_home)),
    ("/", RouteHandler("login", _build_login, None)),
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
    if appbar_key == "login":
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
    app.backbutton.visible = not (troute.match("/") or troute.match("/home"))
    app.login_button.visible = troute.match("/") or troute.match("/home")
    if troute.match("/"):
        app.login_button.content = "Iniciar Sesión"
        app.login_button.icon = None
        app.login_button.style = BOTON_PRINCIPAL
        app.login_button.on_click = app.login
    elif troute.match("/home"):
        app.login_button.content = "Herramientas"
        app.login_button.icon = ft.Icons.SETTINGS
        app.login_button.style = BOTON_SECUNDARIO_SIN
        app.login_button.on_click = lambda _: app.herramientas_dialog.open_dialog()
