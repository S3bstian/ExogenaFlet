import flet as ft
from ui.colors import PINK_200
from ui.buttons import BOTON_PRINCIPAL
from ui.fields import creador_campo_texto
from utils.validators import set_campo_error


class CambioContraDialog:
    def __init__(self, page: ft.Page):
        self.page = page

    def open_dialog(self):
        correo = creador_campo_texto("Ingrese su correo registrado", "")

        def close(_):
            if not correo.value.strip():
                set_campo_error(correo, "Ingrese un correo válido")
                self.page.update()
                return
            # aquí en el futuro iría la lógica de envío del código al correo
            self.page.pop_dialog()
            self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Recuperar contraseña", text_align=ft.TextAlign.CENTER),
            content=ft.Column(
                [correo, ft.Text("Se enviará un código de verificación a su correo electrónico.", size=12)],
                tight=True,
            ),
            actions=[ft.Button(content="Continuar", on_click=close, style=BOTON_PRINCIPAL)],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=ft.Colors.WHITE,
            modal=False,
            shadow_color=PINK_200,
            elevation=15,
            shape=ft.RoundedRectangleBorder(radius=12),
        )

        self.page.show_dialog(dialog)
        self.page.update()
