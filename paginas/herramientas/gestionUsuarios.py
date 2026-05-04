import flet as ft
from core import session
from ui.colors import PINK_50, PINK_200, PINK_400, GREY_700
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO_SIN
from utils.validators import aplicar_validacion_error_text, set_campo_error, validar_campo_obligatorio, validar_email
import time
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

        # --- mensaje interno en el diálogo ---
        self.mensaje = ft.Text("", size=12, color=PINK_400, italic=True, visible=False)

    def mostrar_mensaje(self, texto):
        self.mensaje.value = texto
        self.mensaje.visible = True
        self.dialog.update()
        time.sleep(2.5)
        self.mensaje.visible = False
        self.dialog.update()

    def open_dialog(self):
        self.usuarios_data = self._auth_uc.obtener_usuarios()
        usuario_actual = session.USUARIO_ACTUAL or {"id": None, "nombre": "", "email": ""}
        es_admin = usuario_actual["id"] == 1

        columnas = [
            ft.DataColumn(ft.Text("Nombre")),
            ft.DataColumn(ft.Text("Email")),
        ]
        if es_admin:
            columnas += [
                ft.DataColumn(ft.Text("Activo")),
                ft.DataColumn(ft.Text("Acciones")),
            ]
        else:
            columnas.append(ft.DataColumn(ft.Text("Acciones")))

        filas = []

        # ---- Fila de creación ----
        if self.creando:
            self.crear_nombre = ft.TextField(
                label="Nombre", expand=True, border_color=PINK_200,label_style=ft.TextStyle(color=GREY_700),
            )
            self.crear_email = ft.TextField(
                label="Email", expand=True, border_color=PINK_200, label_style=ft.TextStyle(color=GREY_700),
            )

            acciones = ft.Row(
                [
                    ft.IconButton(
                        icon=ft.Icons.SAVE,
                        tooltip="Guardar",
                        icon_color=PINK_400,
                        style=BOTON_SECUNDARIO_SIN,
                        on_click=lambda e: self.guardar_nuevo(),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CANCEL,
                        tooltip="Cancelar",
                        icon_color=PINK_400,
                        style=BOTON_SECUNDARIO_SIN,
                        on_click=lambda e: self.cancelar_creacion(),
                    ),
                ],
                spacing=6,
            )

            celdas = [
                ft.DataCell(self.crear_nombre),
                ft.DataCell(self.crear_email),
            ]
            if es_admin:
                celdas.append(ft.DataCell(ft.Text("")))
            celdas.append(ft.DataCell(acciones))

            filas.append(ft.DataRow(cells=celdas))

        # ---- Resto de usuarios ----
        for uid, nombre, email, activo in self.usuarios_data:
            if not es_admin and activo != "S":
                continue

            # ---- Modo edición ----
            if self.editando_id == uid:
                self.edit_nombre = ft.TextField(value=nombre, border_color=PINK_200)
                self.edit_email = ft.TextField(value=email, border_color=PINK_200)

                acciones = ft.Row(
                    [
                        ft.IconButton(
                            icon=ft.Icons.SAVE,
                            tooltip="Guardar",
                            icon_color=PINK_400,
                            style=BOTON_SECUNDARIO_SIN,
                            on_click=lambda e, idu=uid: self.guardar_edicion(idu),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.CANCEL,
                            tooltip="Cancelar",
                            icon_color=PINK_400,
                            style=BOTON_SECUNDARIO_SIN,
                            on_click=lambda e: self.cancelar_edicion(),
                        ),
                    ],
                    spacing=6,
                )

                celdas = [
                    ft.DataCell(self.edit_nombre),
                    ft.DataCell(self.edit_email),
                ]
                if es_admin:
                    celdas.append(ft.DataCell(ft.Text("")))
                celdas.append(ft.DataCell(acciones))

                filas.append(ft.DataRow(cells=celdas))
                continue

            # ---- Modo normal ----
            celdas = [
                ft.DataCell(ft.Text(nombre)),
                ft.DataCell(ft.Text(email)),
            ]

            if es_admin:
                chk = ft.Checkbox(
                    value=(activo == "S"),
                    scale=0.9,
                    active_color=PINK_400,
                    overlay_color=ft.Colors.with_opacity(0.8, PINK_50),
                    on_change=lambda e, idu=uid: self._auth_uc.actualizar_activo(
                        "Usuarios", "activo", "Id", idu, e.control.value, -1
                    ),
                )
                btn_modificar = ft.IconButton(
                    icon=ft.Icons.EDIT,
                    tooltip="Modificar usuario",
                    icon_color=PINK_400,
                    style=BOTON_SECUNDARIO_SIN,
                    on_click=lambda e, idu=uid: self.modificar_usuario(idu),
                )
                celdas.append(ft.DataCell(chk))
                celdas.append(ft.DataCell(btn_modificar))
            else:
                if uid == usuario_actual["id"]:
                    btn_modificar = ft.IconButton(
                        icon=ft.Icons.EDIT,
                        tooltip="Modificar usuario",
                        icon_color=PINK_400,
                        style=BOTON_SECUNDARIO_SIN,
                        on_click=lambda e, idu=uid: self.modificar_usuario(idu),
                    )
                    celdas.append(ft.DataCell(btn_modificar))
                else:
                    celdas.append(ft.DataCell(ft.Container()))

            filas.append(ft.DataRow(cells=celdas))

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

        acciones = [
            ft.TextButton(
                content="Cerrar",
                on_click=lambda e: self.page.pop_dialog(),
                style=BOTON_SECUNDARIO_SIN,
            )
        ]
        if es_admin and not self.creando:
            acciones.insert(
                0,
                ft.Button(
                    content="Crear usuario",
                    icon=ft.Icons.ADD,
                    on_click=lambda e: self.crear_usuario(),
                    style=BOTON_PRINCIPAL,
                ),
            )

        self.dialog = ft.AlertDialog(
            title=ft.Text("Gestión de Usuarios", text_align=ft.TextAlign.CENTER),
            content=ft.Container(
                width=750,
                content=ft.Column([
                    ft.ListView(expand=True, controls=[tabla]),
                    ft.Container(height=10),
                    self.mensaje
                ]),
            ),
            bgcolor=ft.Colors.WHITE,
            modal=False,
            shadow_color=PINK_200,
            elevation=15,
            shape=ft.RoundedRectangleBorder(radius=12),
            actions=acciones,
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.show_dialog(self.dialog)
        self.page.update()

    # === MÉTODOS DE EDICIÓN ===
    def modificar_usuario(self, usuario_id: int):
        self.editando_id = usuario_id
        self.open_dialog()

    def cancelar_edicion(self):
        self.editando_id = None
        self.open_dialog()

    def guardar_edicion(self, usuario_id: int):
        nuevo_nombre = self.edit_nombre.value.strip()
        nuevo_email = self.edit_email.value.strip()

        # Limpiar errores previos (Flet 0.80: TextField usa .error)
        set_campo_error(self.edit_nombre, None)
        set_campo_error(self.edit_email, None)
        
        errores = False

        # Validar nombre obligatorio
        if not aplicar_validacion_error_text(self.edit_nombre, nuevo_nombre, validar_campo_obligatorio, nombre_campo="Nombre"):
            errores = True
        
        # Validar email obligatorio y formato
        if not aplicar_validacion_error_text(self.edit_email, nuevo_email, validar_campo_obligatorio, nombre_campo="Email"):
            errores = True
        elif not aplicar_validacion_error_text(self.edit_email, nuevo_email, validar_email):
            errores = True

        if errores:
            self.mostrar_mensaje("Revise los campos marcados con error")
            self.dialog.update()
            return

        if self._auth_uc.crear_o_actualizar_usuario(usuario_id, nuevo_nombre, nuevo_email):
            self.mostrar_mensaje("Usuario actualizado correctamente")
            self.editando_id = None
            self.open_dialog()
        else:
            self.mostrar_mensaje("Error al actualizar usuario")

    # === CREAR USUARIO EN TABLA ===
    def crear_usuario(self):
        self.creando = True
        self.open_dialog()

    def cancelar_creacion(self):
        self.creando = False
        self.open_dialog()

    def guardar_nuevo(self):
        nombre = self.crear_nombre.value.strip()
        email = self.crear_email.value.strip()

        # Limpiar errores previos (Flet 0.80: TextField usa .error)
        set_campo_error(self.crear_nombre, None)
        set_campo_error(self.crear_email, None)
        
        errores = False

        # Validar nombre obligatorio
        if not aplicar_validacion_error_text(self.crear_nombre, nombre, validar_campo_obligatorio, nombre_campo="Nombre"):
            errores = True
        
        # Validar email obligatorio y formato
        if not aplicar_validacion_error_text(self.crear_email, email, validar_campo_obligatorio, nombre_campo="Email"):
            errores = True
        elif not aplicar_validacion_error_text(self.crear_email, email, validar_email):
            errores = True

        if errores:
            self.mostrar_mensaje("Revise los campos marcados con error")
            self.dialog.update()
            return

        if self._auth_uc.crear_o_actualizar_usuario(None, nombre, email):
            self.mostrar_mensaje("Usuario creado correctamente")
            self.creando = False
            self.open_dialog()
        else:
            self.mostrar_mensaje("Error al crear usuario")
