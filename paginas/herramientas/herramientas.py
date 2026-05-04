import asyncio
import random
import flet as ft
from paginas.herramientas.acercaDe import AcercaDeDialog
from paginas.herramientas.gestionUsuarios import GestionUsuariosDialog
from ui.colors import PINK_100, WHITE
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO
from utils.paths import IMG_PATH

class HerramientasDialog:
    def __init__(self, page, container):
        self.page = page
        self.dialog = None
        self.acerca_de_dialog = AcercaDeDialog(page)
        self.usuarios_dialog = GestionUsuariosDialog(page, container=container)

    def hover_effect(self, e):
        if e.data == True:
            # Rotación aleatoria entre -0.1 y 0.1 radianes (~-6° a 6°)
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

    def open_dialog(self):
        yutu = ft.Container(
            content=ft.Image(src=IMG_PATH + "/Helisa-Youtube.png"),
            on_click=lambda e: asyncio.create_task(
                self.page.launch_url("https://www.youtube.com/playlist?list=PL2xp6IRDj-RWsVvccHn7dC8bCsMgosgrK")
            ),
            on_hover=self.hover_effect,
            animate_scale=ft.Animation(300, ft.AnimationCurve.BOUNCE_OUT),
            animate_rotation=ft.Animation(400, ft.AnimationCurve.BOUNCE_OUT),
            padding=10,
        )

        ayudas = ft.Container(
            content=ft.Image(src=IMG_PATH + "/Ayudas.png"),
            on_click=lambda e: asyncio.create_task(
                self.page.launch_url("https://helisa.com/actualizacion/informacion-exogena/")
            ),
            on_hover=self.hover_effect,
            animate_scale=ft.Animation(300, ft.AnimationCurve.BOUNCE_OUT),
            animate_rotation=ft.Animation(400, ft.AnimationCurve.BOUNCE_OUT),
            padding=10,
        )
        gestion_user_btn = ft.ElevatedButton(
            "Gestion Usuarios",
            icon=ft.Icons.VERIFIED_USER_SHARP,
            style=BOTON_SECUNDARIO,
            on_click=lambda e: self.usuarios_dialog.open_dialog(),
        )
        parametros = ft.ElevatedButton(
            "Parámetros", 
            icon=ft.Icons.EDIT_ATTRIBUTES_OUTLINED,
            on_click=lambda e: print("parámetros"),
            style=BOTON_SECUNDARIO
        )
        acerca_de_btn = ft.ElevatedButton(
            "Acerca de",
            icon=ft.Icons.INFO_OUTLINE_ROUNDED,
            style=BOTON_SECUNDARIO,
            on_click=lambda e: self.acerca_de_dialog.open_dialog(),
        )
        logout_btn = ft.ElevatedButton(
            "Cerrar sesión",
            icon=ft.Icons.LOGOUT_SHARP,
            style=BOTON_PRINCIPAL,
            on_click=self.logout
        )
        columna_izquierda = ft.Column(
            controls=[yutu, ayudas],
            tight=True,
            wrap=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
        
        columna_derecha = ft.Column(
            controls=[gestion_user_btn, parametros, acerca_de_btn, logout_btn],
            tight=True,
            wrap=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
        
        self.dialog = ft.AlertDialog(
            title=ft.Text("Herramientas"),
            content=ft.Row(
                [columna_izquierda, columna_derecha],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            bgcolor=WHITE,
        )
        self.page.show_dialog(self.dialog)

    def logout(self, e):
        from core import session
        session.USUARIO_ACTUAL = None
        session.EMPRESA_ACTUAL = None
        self.page.pop_dialog()  # Cerrar el diálogo de manera segura
        self.page.update()
        # Limpiar vistas y navegar a la página de login
        # Se hace después de cerrar el diálogo para evitar conflictos
        if self.page.views:
            self.page.views.clear()
        asyncio.create_task(self.page.push_route("/"))
        
