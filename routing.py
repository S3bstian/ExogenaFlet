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
ViewInstance = Optional[Any]
BuildViewFn = Callable[[ft.Page, Any], Tuple[ft.Control, ViewInstance]]
OnEnterFn = Optional[Callable[[ft.Page, Any], None]]

@dataclass
class RouteHandler:
    appbar: str
    build_view: BuildViewFn
    on_enter: OnEnterFn = None


def _build_page(page_cls: type, page: ft.Page, app: Any) -> Tuple[ft.Control, Any]:
    """Construye una página por clase y retorna su vista junto con la instancia."""
    page_instance = page_cls(page, app)
    return page_instance.view(), page_instance


def _build_login(_page: ft.Page, app: Any) -> Tuple[ft.Control, None]:
    """Builder de la ruta raíz: renderiza solo el mensaje base del login."""
    return (app.msg, None)


def _builder_pagina(page_cls: type) -> BuildViewFn:
    """Crea un builder de ruta para una clase de página concreta."""
    return lambda page, app: _build_page(page_cls, page, app)


def _configurar_teclado_pagina(page: ft.Page, view_instance: Any) -> None:
    """Asigna el handler global de teclado cuando la vista lo requiere."""
    page.on_keyboard_event = view_instance._on_keyboard_page


def _on_enter_con_teclado(page: ft.Page, vi: Any) -> None:
    """Activa atajos de teclado globales para la vista activa."""
    _configurar_teclado_pagina(page, vi)


def _on_enter_cartilla(page: ft.Page, vi: Any) -> None:
    _on_enter_con_teclado(page, vi)
    vi.cargar_terceros()


def _on_enter_hoja(page: ft.Page, vi: Any) -> None:
    # Flet: un solo handler global; en esta ruta la hoja captura atajos de teclado.
    _on_enter_con_teclado(page, vi)
    vi.cargar_conceptos()
    vi.cargar_datos()


def _on_enter_toma(page: ft.Page, vi: Any) -> None:
    _on_enter_con_teclado(page, vi)


def _on_enter_formatos(_page: ft.Page, vi: Any) -> None:
    vi.actualizar_formatos()


def _on_enter_generar(_page: ft.Page, vi: Any) -> None:
    vi._cargar_formatos_y_abrir_dialogo()


def _on_enter_home(_page: ft.Page, vi: Any) -> None:
    vi._aplicar_carga_empresas()


# Orden: más específico primero para el match
RUTAS: list[Tuple[str, RouteHandler]] = [
    ("/home/generar_xml", RouteHandler(APPBAR_HOME, _builder_pagina(GenerarXmlPage), _on_enter_generar)),
    ("/home/hoja_trabajo", RouteHandler(APPBAR_HOME, _builder_pagina(HojaTrabajoPage), _on_enter_hoja)),
    ("/home/cartilla_terceros", RouteHandler(APPBAR_HOME, _builder_pagina(CartillaTercerosPage), _on_enter_cartilla)),
    ("/home/toma_informacion", RouteHandler(APPBAR_HOME, _builder_pagina(TomaInformacionPage), _on_enter_toma)),
    ("/home/formatos_conceptos", RouteHandler(APPBAR_HOME, _builder_pagina(FormatosPage), _on_enter_formatos)),
    ("/home", RouteHandler(APPBAR_HOME, _builder_pagina(HomePage), _on_enter_home)),
    ("/", RouteHandler(APPBAR_LOGIN, _build_login, None)),
]


def resolve_route(troute: ft.TemplateRoute) -> Optional[Tuple[str, RouteHandler]]:
    """Resuelve la primera ruta registrada que haga match con la URL actual."""
    for ruta_registrada, manejador in RUTAS:
        if troute.match(ruta_registrada):
            return (ruta_registrada, manejador)
    return None


def parent_route_for_back(route: str) -> Optional[str]:
    """Ruta padre al usar Atrás: solo las pantallas bajo /home/... vuelven a /home."""
    if route.startswith("/home/"):
        return "/home"
    return None


def _fila_appbar_login(app: Any) -> ft.Row:
    """Fila superior del appbar en login/home con logo grande centrado."""
    return ft.Row(
        controls=[
            app.logo_helisa,
            ft.Container(expand=True),
            app.backbutton,
            app.login_button,
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _contenido_appbar_login(app: Any) -> ft.Control:
    """Contenido completo del appbar para la pantalla de login."""
    return ft.Column([_fila_appbar_login(app)], alignment=ft.MainAxisAlignment.CENTER)


def _fila_appbar_home(app: Any) -> ft.Row:
    """Fila superior del appbar compacto para rutas hijas de home."""
    return ft.Row(
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
    )


def _logo_appbar_home() -> ft.Image:
    """Logo anclado a la izquierda para appbar compacto."""
    return ft.Image(
        src=IMG_PATH + "/helisa.png",
        width=130,
        height=75,
        fit=ft.BoxFit.CONTAIN,
        left=0,
        top=(55 - 75) / 2,
    )


def _contenido_appbar_home(app: Any) -> ft.Control:
    """Contenido del appbar para rutas bajo /home."""
    return ft.Stack(
        expand=True,
        height=130,
        clip_behavior=ft.ClipBehavior.NONE,
        controls=[_fila_appbar_home(app), _logo_appbar_home()],
    )


def get_appbar_content(appbar_key: str, app: Any) -> Tuple[int, ft.Control]:
    """Devuelve alto y contenido del appbar según el tipo de ruta."""
    if appbar_key == APPBAR_LOGIN:
        return (666, _contenido_appbar_login(app))
    return (55, _contenido_appbar_home(app))


def _configurar_boton_login_en_login(app: Any) -> None:
    """Configura botón principal para iniciar sesión."""
    _configurar_boton_topbar(
        app=app,
        texto="Iniciar Sesión",
        icono=None,
        estilo=BOTON_PRINCIPAL,
        on_click=app.login,
    )


def _configurar_boton_login_en_home(app: Any) -> None:
    """Configura botón secundario para abrir herramientas en home."""
    _configurar_boton_topbar(
        app=app,
        texto="Herramientas",
        icono=ft.Icons.SETTINGS,
        estilo=BOTON_SECUNDARIO_SIN,
        on_click=lambda _: app.herramientas_dialog.open_dialog(),
    )


def _configurar_boton_topbar(
    app: Any,
    texto: str,
    icono: Any,
    estilo: Any,
    on_click: Callable[..., None],
) -> None:
    """Aplica configuración visual y handler del botón de acción en topbar."""
    app.login_button.content = texto
    app.login_button.icon = icono
    app.login_button.style = estilo
    app.login_button.on_click = on_click


def update_topbar(troute: ft.TemplateRoute, app: Any) -> None:
    """Sincroniza visibilidad y comportamiento de botones según la ruta activa."""
    esta_en_login = troute.match("/")
    esta_en_home = troute.match("/home")
    app.backbutton.visible = not (esta_en_login or esta_en_home)
    app.login_button.visible = esta_en_login or esta_en_home
    if esta_en_login:
        _configurar_boton_login_en_login(app)
    elif esta_en_home:
        _configurar_boton_login_en_home(app)
