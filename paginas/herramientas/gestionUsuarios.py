import flet as ft
from core import session
from ui.colors import PINK_50, PINK_200, PINK_400, GREY_700
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO_SIN
from utils.validators import aplicar_validacion_error_text, set_campo_error, validar_campo_obligatorio, validar_email

_MENSAJE_FLASH_SEG = 2.5
_TABLA_LISTVIEW_ANCHO = 750


class GestionUsuariosDialog:
    def __init__(self, page, *, container):
        self.page = page
        self._auth_uc = container.auth_uc
        self.dialog = None
        self.usuarios_data = []
        self.editando_id = None
        self.edit_nombre = None
        self.edit_email = None
        self.creando = False
        self.crear_nombre = None
        self.crear_email = None
        self.mensaje = ft.Text("", size=12, color=PINK_400, italic=True, visible=False)

    @staticmethod
    def _usuario_en_sesion() -> dict:
        return session.USUARIO_ACTUAL or {"id": None, "nombre": "", "email": ""}

    @staticmethod
    def _es_admin(usuario_actual: dict) -> bool:
        return usuario_actual.get("id") == 1

    def _campo_texto_usuario(self, *, label: str, value: str = "", expand: bool = True) -> ft.TextField:
        return ft.TextField(
            label=label,
            value=value,
            expand=expand,
            border_color=PINK_200,
            label_style=ft.TextStyle(color=GREY_700),
        )

    def _fila_acciones_editor(self, on_guardar, on_cancelar) -> ft.Row:
        return ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.SAVE,
                    tooltip="Guardar",
                    icon_color=PINK_400,
                    style=BOTON_SECUNDARIO_SIN,
                    on_click=on_guardar,
                ),
                ft.IconButton(
                    icon=ft.Icons.CANCEL,
                    tooltip="Cancelar",
                    icon_color=PINK_400,
                    style=BOTON_SECUNDARIO_SIN,
                    on_click=on_cancelar,
                ),
            ],
            spacing=6,
        )

    def _programar_ocultar_mensaje(self, segundos: float = _MENSAJE_FLASH_SEG) -> None:
        """Oculta el mensaje tras un delay sin bloquear el hilo de UI."""
        conn = getattr(getattr(self.page, "session", None), "connection", None)
        loop = getattr(conn, "loop", None) if conn else None
        if loop is None:
            return

        def ocultar():
            self.mensaje.visible = False
            if self.dialog:
                try:
                    self.dialog.update()
                except Exception:
                    pass

        loop.call_later(segundos, ocultar)

    def mostrar_mensaje(self, texto: str):
        self.mensaje.value = texto
        self.mensaje.visible = True
        if self.dialog:
            self.dialog.update()
        self._programar_ocultar_mensaje()

    def _columnas_tabla_usuarios(self, es_admin: bool) -> list[ft.DataColumn]:
        cols = [
            ft.DataColumn(ft.Text("Nombre")),
            ft.DataColumn(ft.Text("Email")),
        ]
        if es_admin:
            cols.extend(
                [
                    ft.DataColumn(ft.Text("Activo")),
                    ft.DataColumn(ft.Text("Acciones")),
                ]
            )
        else:
            cols.append(ft.DataColumn(ft.Text("Acciones")))
        return cols

    def _append_celdas_placeholder_admin(self, celdas: list, es_admin: bool):
        """En filas de edición/creación la columna Activo queda vacía."""
        if es_admin:
            celdas.append(ft.DataCell(ft.Text("")))

    def _fila_creacion(self, es_admin: bool) -> ft.DataRow:
        self.crear_nombre = self._campo_texto_usuario(label="Nombre")
        self.crear_email = self._campo_texto_usuario(label="Email")
        acciones = self._fila_acciones_editor(
            lambda _e: self.guardar_nuevo(),
            lambda _e: self.cancelar_creacion(),
        )
        celdas = [
            ft.DataCell(self.crear_nombre),
            ft.DataCell(self.crear_email),
        ]
        self._append_celdas_placeholder_admin(celdas, es_admin)
        celdas.append(ft.DataCell(acciones))
        return ft.DataRow(cells=celdas)

    def _fila_edicion(self, uid: int, nombre: str, email: str, es_admin: bool) -> ft.DataRow:
        self.edit_nombre = ft.TextField(value=nombre, border_color=PINK_200)
        self.edit_email = ft.TextField(value=email, border_color=PINK_200)
        acciones = self._fila_acciones_editor(
            lambda _e, idu=uid: self.guardar_edicion(idu),
            lambda _e: self.cancelar_edicion(),
        )
        celdas = [
            ft.DataCell(self.edit_nombre),
            ft.DataCell(self.edit_email),
        ]
        self._append_celdas_placeholder_admin(celdas, es_admin)
        celdas.append(ft.DataCell(acciones))
        return ft.DataRow(cells=celdas)

    def _checkbox_activo(self, uid: int, activo: str) -> ft.Checkbox:
        return ft.Checkbox(
            value=(activo == "S"),
            scale=0.9,
            active_color=PINK_400,
            overlay_color=ft.Colors.with_opacity(0.8, PINK_50),
            on_change=lambda e, idu=uid: self._auth_uc.actualizar_activo(
                "Usuarios", "activo", "Id", idu, e.control.value, -1
            ),
        )

    def _boton_modificar(self, uid: int) -> ft.IconButton:
        return ft.IconButton(
            icon=ft.Icons.EDIT,
            tooltip="Modificar usuario",
            icon_color=PINK_400,
            style=BOTON_SECUNDARIO_SIN,
            on_click=lambda _e, idu=uid: self.modificar_usuario(idu),
        )

    def _fila_usuario_lectura(
        self,
        uid: int,
        nombre: str,
        email: str,
        activo: str,
        es_admin: bool,
        usuario_actual: dict,
    ) -> ft.DataRow:
        celdas = [
            ft.DataCell(ft.Text(nombre)),
            ft.DataCell(ft.Text(email)),
        ]
        if es_admin:
            celdas.append(ft.DataCell(self._checkbox_activo(uid, activo)))
            celdas.append(ft.DataCell(self._boton_modificar(uid)))
        elif uid == usuario_actual["id"]:
            celdas.append(ft.DataCell(self._boton_modificar(uid)))
        else:
            celdas.append(ft.DataCell(ft.Container()))
        return ft.DataRow(cells=celdas)

    def _construir_filas_tabla(self, es_admin: bool, usuario_actual: dict) -> list[ft.DataRow]:
        filas: list[ft.DataRow] = []
        if self.creando:
            filas.append(self._fila_creacion(es_admin))

        for uid, nombre, email, activo in self.usuarios_data:
            if not es_admin and activo != "S":
                continue
            if self.editando_id == uid:
                filas.append(self._fila_edicion(uid, nombre, email, es_admin))
                continue
            filas.append(self._fila_usuario_lectura(uid, nombre, email, activo, es_admin, usuario_actual))
        return filas

    def _actions_bar(self, es_admin: bool) -> list:
        acciones = [
            ft.TextButton(
                content="Cerrar",
                on_click=lambda _e: self.page.pop_dialog(),
                style=BOTON_SECUNDARIO_SIN,
            )
        ]
        if es_admin and not self.creando:
            acciones.insert(
                0,
                ft.Button(
                    content="Crear usuario",
                    icon=ft.Icons.ADD,
                    on_click=lambda _e: self.crear_usuario(),
                    style=BOTON_PRINCIPAL,
                ),
            )
        return acciones

    def _validar_nombre_y_email(self, campo_nombre: ft.TextField, campo_email: ft.TextField) -> tuple[str, str] | None:
        """Retorna (nombre, email) normalizados o None si hay errores de validación."""
        nombre = campo_nombre.value.strip()
        email = campo_email.value.strip()
        set_campo_error(campo_nombre, None)
        set_campo_error(campo_email, None)
        errores = False
        if not aplicar_validacion_error_text(
            campo_nombre, nombre, validar_campo_obligatorio, nombre_campo="Nombre"
        ):
            errores = True
        if not aplicar_validacion_error_text(
            campo_email, email, validar_campo_obligatorio, nombre_campo="Email"
        ):
            errores = True
        elif not aplicar_validacion_error_text(campo_email, email, validar_email):
            errores = True
        if errores:
            self.mostrar_mensaje("Revise los campos marcados con error")
            if self.dialog:
                self.dialog.update()
            return None
        return nombre, email

    def open_dialog(self):
        self.usuarios_data = self._auth_uc.obtener_usuarios()
        usuario_actual = self._usuario_en_sesion()
        es_admin = self._es_admin(usuario_actual)

        columnas = self._columnas_tabla_usuarios(es_admin)
        filas = self._construir_filas_tabla(es_admin, usuario_actual)

        tabla = ft.DataTable(
            columns=columnas,
            rows=filas,
            column_spacing=20,
            heading_row_height=44,
            data_row_max_height=47,
            heading_row_color=PINK_50,
            border=ft.border.all(0.5, PINK_200),
            divider_thickness=0.5,
        )

        self.dialog = ft.AlertDialog(
            title=ft.Text("Gestión de Usuarios", text_align=ft.TextAlign.CENTER),
            content=ft.Container(
                width=_TABLA_LISTVIEW_ANCHO,
                content=ft.Column(
                    [
                        ft.ListView(expand=True, controls=[tabla]),
                        ft.Container(height=10),
                        self.mensaje,
                    ],
                ),
            ),
            bgcolor=ft.Colors.WHITE,
            modal=False,
            shadow_color=PINK_200,
            elevation=15,
            shape=ft.RoundedRectangleBorder(radius=12),
            actions=self._actions_bar(es_admin),
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.show_dialog(self.dialog)
        self.page.update()

    def modificar_usuario(self, usuario_id: int):
        self.editando_id = usuario_id
        self.open_dialog()

    def cancelar_edicion(self):
        self.editando_id = None
        self.open_dialog()

    def guardar_edicion(self, usuario_id: int):
        datos = self._validar_nombre_y_email(self.edit_nombre, self.edit_email)
        if datos is None:
            return
        nuevo_nombre, nuevo_email = datos
        if self._auth_uc.crear_o_actualizar_usuario(usuario_id, nuevo_nombre, nuevo_email):
            self.mostrar_mensaje("Usuario actualizado correctamente")
            self.editando_id = None
            self.open_dialog()
        else:
            self.mostrar_mensaje("Error al actualizar usuario")

    def crear_usuario(self):
        self.creando = True
        self.open_dialog()

    def cancelar_creacion(self):
        self.creando = False
        self.open_dialog()

    def guardar_nuevo(self):
        datos = self._validar_nombre_y_email(self.crear_nombre, self.crear_email)
        if datos is None:
            return
        nombre, email = datos
        if self._auth_uc.crear_o_actualizar_usuario(None, nombre, email):
            self.mostrar_mensaje("Usuario creado correctamente")
            self.creando = False
            self.open_dialog()
        else:
            self.mostrar_mensaje("Error al crear usuario")
