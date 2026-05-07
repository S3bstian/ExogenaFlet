import asyncio
import random
import flet as ft
from paginas.herramientas.acercaDe import AcercaDeDialog
from paginas.herramientas.gestionUsuarios import GestionUsuariosDialog
from ui.colors import PINK_100, WHITE
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO
from utils.paths import IMG_PATH


_URL_PLAYLIST_YOUTUBE = "https://www.youtube.com/playlist?list=PL2xp6IRDj-RWsVvccHn7dC8bCsMgosgrK"
_URL_AYUDAS_HELISA = "https://helisa.com/actualizacion/informacion-exogena/"
_ANIM_HOVER_ESC = ft.Animation(300, ft.AnimationCurve.BOUNCE_OUT)
_ANIM_HOVER_ROT = ft.Animation(400, ft.AnimationCurve.BOUNCE_OUT)


class HerramientasDialog:
    def __init__(self, page, container):
        self.page = page
        self.dialog = None
        self.acerca_de_dialog = AcercaDeDialog(page)
        self.usuarios_dialog = GestionUsuariosDialog(page, container=container)

    def hover_effect(self, e):
        if e.data is True:
            e.control.rotate = random.uniform(-0.1, 0.1)
            e.control.scale = 1.05
            e.control.shadow = ft.BoxShadow(
                blur_radius=55, spread_radius=0.1, color=ft.Colors.with_opacity(0.5, PINK_100)
            )
        else:
            e.control.rotate = 0
            e.control.scale = 1.0
            e.control.shadow = None
        e.control.update()

    def _abrir_url(self, url: str) -> None:
        asyncio.create_task(self.page.launch_url(url))

    def _bloque_imagen_link(self, imagen_archivo: str, url: str) -> ft.Container:
        """Imagen clicable que abre URL externa en el navegador predeterminado."""
        src = f"{IMG_PATH}/{imagen_archivo}"
        return ft.Container(
            content=ft.Image(src=src),
            on_click=lambda _e: self._abrir_url(url),
            on_hover=self.hover_effect,
            animate_scale=_ANIM_HOVER_ESC,
            animate_rotation=_ANIM_HOVER_ROT,
            padding=10,
        )

    def _columna_enlaces_medios(self) -> ft.Column:
        return ft.Column(
            controls=[
                self._bloque_imagen_link("Helisa-Youtube.png", _URL_PLAYLIST_YOUTUBE),
                self._bloque_imagen_link("Ayudas.png", _URL_AYUDAS_HELISA),
            ],
            tight=True,
            wrap=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _columna_botones_internos(self) -> ft.Column:
        return ft.Column(
            controls=[
                ft.ElevatedButton(
                    "Gestion Usuarios",
                    icon=ft.Icons.VERIFIED_USER_SHARP,
                    style=BOTON_SECUNDARIO,
                    on_click=lambda _e: self.usuarios_dialog.open_dialog(),
                ),
                ft.ElevatedButton(
                    "Parámetros",
                    icon=ft.Icons.EDIT_ATTRIBUTES_OUTLINED,
                    on_click=lambda _e: print("parámetros"),
                    style=BOTON_SECUNDARIO,
                ),
                ft.ElevatedButton(
                    "Acerca de",
                    icon=ft.Icons.INFO_OUTLINE_ROUNDED,
                    style=BOTON_SECUNDARIO,
                    on_click=lambda _e: self.acerca_de_dialog.open_dialog(),
                ),
                ft.ElevatedButton(
                    "Cerrar sesión",
                    icon=ft.Icons.LOGOUT_SHARP,
                    style=BOTON_PRINCIPAL,
                    on_click=self.logout,
                ),
            ],
            tight=True,
            wrap=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def open_dialog(self):
        self.dialog = ft.AlertDialog(
            title=ft.Text("Herramientas"),
            content=ft.Row(
                [self._columna_enlaces_medios(), self._columna_botones_internos()],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            bgcolor=WHITE,
        )
        self.page.show_dialog(self.dialog)

    def logout(self, e):
        from core import session

        session.USUARIO_ACTUAL = None
        session.EMPRESA_ACTUAL = None
        self.page.pop_dialog()
        self.page.update()
        if self.page.views:
            self.page.views.clear()
        asyncio.create_task(self.page.push_route("/"))
