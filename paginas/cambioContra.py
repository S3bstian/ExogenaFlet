import flet as ft
from ui.colors import PINK_200
from ui.buttons import BOTON_PRINCIPAL
from ui.fields import creador_campo_texto
from utils.validators import set_campo_error


_TEXTO_AVISO_CORREO = "Se enviará un código de verificación a su correo electrónico."


class CambioContraDialog:
    def __init__(self, page: ft.Page):
        self.page = page

    def _validar_correo_no_vacio(self, campo_correo: ft.TextField) -> bool:
        """Exige texto en el campo; marca error visible si falta."""
        if campo_correo.value and campo_correo.value.strip():
            return True
        set_campo_error(campo_correo, "Ingrese un correo válido")
        return False

    def _on_continuar(self, campo_correo: ft.TextField, _event):
        if not self._validar_correo_no_vacio(campo_correo):
            self.page.update()
            return
        # Aquí en el futuro iría la lógica de envío del código al correo.
        self.page.pop_dialog()
        self.page.update()

    def _build_dialog(self, campo_correo: ft.TextField) -> ft.AlertDialog:
        return ft.AlertDialog(
            title=ft.Text("Recuperar contraseña", text_align=ft.TextAlign.CENTER),
            content=ft.Column(
                [
                    campo_correo,
                    ft.Text(_TEXTO_AVISO_CORREO, size=12),
                ],
                tight=True,
            ),
            actions=[
                ft.Button(
                    content="Continuar",
                    on_click=lambda e: self._on_continuar(campo_correo, e),
                    style=BOTON_PRINCIPAL,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=ft.Colors.WHITE,
            modal=False,
            shadow_color=PINK_200,
            elevation=15,
            shape=ft.RoundedRectangleBorder(radius=12),
        )

    def open_dialog(self):
        campo_correo = creador_campo_texto("Ingrese su correo registrado", "")
        dialog = self._build_dialog(campo_correo)
        self.page.show_dialog(dialog)
        self.page.update()
