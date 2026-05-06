import flet as ft
from core.settings import PERIODO
from ui.colors import WHITE
from ui.buttons import BOTON_SECUNDARIO_SIN
from utils.paths import IMG_PATH


_LOGO_EXOGENA = "Logo-Exogena.png"
_LOGO_HELISA = "helisa.png"
_AVISO_LEGAL_TEXTO = [
    "Derechos Reservados de Autor",
    "HELISA es marca registrada",
    "Proasistemas S.A. miembros de FEDESOFT",
    "Bogotá D.C., Colombia 2025",
]


class AcercaDeDialog:
    def __init__(self, page: ft.Page):
        self.page = page
        self.dialog = None

    def _titulo_producto(self) -> ft.Text:
        return ft.Text(
            f"Helisa Información Exógena {PERIODO} Versión 1.0.0",
            size=14,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.BLACK87,
        )

    def _columna_texto_info(self) -> ft.Column:
        return ft.Column(
            [
                self._titulo_producto(),
                *[
                    ft.Text(linea, size=13, color=ft.Colors.BLACK87)
                    for linea in _AVISO_LEGAL_TEXTO
                ],
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=3,
        )

    def _bloque_logo(
        self,
        archivo: str,
        *,
        width: float,
        height: float,
        expand: bool = False,
        padding_top: float | None = None,
    ) -> ft.Container:
        img = ft.Image(
            src=f"{IMG_PATH}/{archivo}",
            width=width,
            height=height,
            fit=ft.BoxFit.CONTAIN,
        )
        kwargs: dict = dict(
            content=img,
            alignment=ft.Alignment(0, 0),
            expand=expand,
        )
        if padding_top is not None:
            kwargs["padding"] = ft.padding.only(top=padding_top)
        return ft.Container(**kwargs)

    def _cuerpo_filas_principal(self) -> ft.Row:
        return ft.Row(
            [
                self._bloque_logo(_LOGO_EXOGENA, width=250, height=250, expand=True),
                self._columna_texto_info(),
            ],
            alignment=ft.MainAxisAlignment.SPACE_EVENLY,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )

    def _contenido_completo(self) -> ft.Column:
        return ft.Column(
            [
                ft.Text("Acerca de...", size=16, weight=ft.FontWeight.BOLD),
                self._cuerpo_filas_principal(),
                self._bloque_logo(_LOGO_HELISA, width=250, height=100, padding_top=20),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
            expand=True,
        )

    def _alert_acerca_de(self, contenido: ft.Column) -> ft.AlertDialog:
        return ft.AlertDialog(
            modal=True,
            content_padding=ft.Padding.all(20),
            bgcolor=WHITE,
            content=contenido,
            actions=[
                ft.TextButton(
                    content="Cerrar",
                    style=BOTON_SECUNDARIO_SIN,
                    on_click=lambda _e: self.cerrar(),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def open_dialog(self):
        self.dialog = self._alert_acerca_de(self._contenido_completo())
        self.page.show_dialog(self.dialog)

    def cerrar(self):
        if self.dialog:
            self.page.pop_dialog()
            self.page.update()
