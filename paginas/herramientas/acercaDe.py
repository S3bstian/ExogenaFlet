import flet as ft
from core.settings import PERIODO
from ui.colors import WHITE
from ui.buttons import BOTON_SECUNDARIO_SIN
from utils.paths import IMG_PATH

class AcercaDeDialog:
    def __init__(self, page):
        self.page = page
        self.dialog = None

    def open_dialog(self):
        # Logo principal de Información Exógena
        logo_exogena = ft.Container(
            content=ft.Image(
                src=IMG_PATH + "/Logo-Exogena.png",
                width=250,
                height=250,
                fit=ft.BoxFit.CONTAIN
            ),
            alignment=ft.Alignment(0, 0),
            expand=True
        )

        # Texto informativo (parte derecha)
        texto_info = ft.Column(
            [
                ft.Text(
                    f"Helisa Información Exógena {PERIODO} Versión 1.0.0",
                    size=14,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.BLACK87
                ),
                ft.Text("Derechos Reservados de Autor", size=13, color=ft.Colors.BLACK87),
                ft.Text("HELISA es marca registrada", size=13, color=ft.Colors.BLACK87),
                ft.Text("Proasistemas S.A. miembros de FEDESOFT", size=13, color=ft.Colors.BLACK87),
                ft.Text("Bogotá D.C., Colombia 2025", size=13, color=ft.Colors.BLACK87),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=3
        )

        # Logo de Helisa (abajo)
        logo_helisa = ft.Container(
            content=ft.Image(
                src=IMG_PATH + "/helisa.png",
                width=250,
                height=100,
                fit=ft.BoxFit.CONTAIN
            ),
            alignment=ft.Alignment(0, 0),
            padding=ft.padding.only(top=20)
        )

        # Cuerpo del diálogo (dos columnas principales)
        cuerpo = ft.Row(
            [
                logo_exogena,
                texto_info
            ],
            alignment=ft.MainAxisAlignment.SPACE_EVENLY,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True
        )

        contenido = ft.Column(
            [
                ft.Text("Acerca de...", size=16, weight=ft.FontWeight.BOLD),
                cuerpo,
                logo_helisa
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
            expand=True
        )

        # Construcción del diálogo
        self.dialog = ft.AlertDialog(
            modal=True,
            content_padding=ft.Padding.all(20),
            bgcolor=WHITE,
            content=contenido,
            actions=[
                ft.TextButton(content="Cerrar", style=BOTON_SECUNDARIO_SIN, on_click=lambda e: self.cerrar())
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.show_dialog(self.dialog)

    def cerrar(self):
        if self.dialog:
            self.page.pop_dialog()
            self.page.update()
