import flet as ft
from core import session
from core.settings import PERIODO
from ui.colors import PINK_50, PINK_200, WHITE
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO, BOTON_SECUNDARIO_SIN
import zipfile
import os
class CopiasDialog:
    def __init__(self, page, container):
        self.page = page
        self._empresas_uc = container.empresas_uc
        self._helisa_uc = container.helisa_uc
        self.checks_empresas = []
        self.mensaje = ft.Text("", size=14, italic=True, visible=False, text_align=ft.TextAlign.CENTER)
        self.contenedor_dinamico = ft.Column([], tight=True, spacing=15)

        self.dialog = ft.AlertDialog(
            modal=False,
            title=ft.Text("Copias de Seguridad"),
            content=ft.Column(
                [
                    self.contenedor_dinamico,
                    self.mensaje
                ],
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                scroll=ft.ScrollMode.HIDDEN
            ),
            bgcolor=WHITE,
            shadow_color=PINK_200,
            elevation=15,
        )

    def _mostrar_mensaje(self, texto: str) -> None:
        """Muestra feedback persistente en el diálogo actual."""
        self.mensaje.value = texto
        self.mensaje.visible = True
        self.page.update()

    def _ocultar_mensaje(self) -> None:
        self.mensaje.visible = False

    def _ruta_archivo_empresa(self, codigo_empresa: int) -> str:
        codigo = str(codigo_empresa).zfill(2)
        return os.path.join(self._ruta_ex, f"HELI{codigo}BD.EXG")

    def _crear_check_empresa(self, empresa: dict) -> ft.Checkbox:
        chk = ft.Checkbox(
            label=f"{empresa['codigo']} - {empresa['nombre']}",
            active_color=PINK_200,
            check_color=WHITE,
        )
        chk.ruta_archivo = self._ruta_archivo_empresa(empresa["codigo"])
        return chk

    @staticmethod
    def _crear_boton_menu(texto: str, icono: str, accion, estilo) -> ft.ElevatedButton:
        return ft.ElevatedButton(
            texto,
            on_click=accion,
            icon=icono,
            style=estilo,
            width=250,
            height=60,
        )

    def _menu_principal_controles(self, estilo_boton) -> list[ft.Control]:
        return [
            self._crear_boton_menu(
                "Generar copia",
                ft.Icons.BACKUP_OUTLINED,
                self.generar_copia,
                estilo_boton,
            ),
            self._crear_boton_menu(
                "Restaurar copia",
                ft.Icons.RESTORE_OUTLINED,
                self.restaurar_copia,
                estilo_boton,
            ),
        ]

    def _render_menu_principal(self, *, estilo_boton) -> None:
        self.contenedor_dinamico.controls = self._menu_principal_controles(estilo_boton)
        self.page.update()

    @staticmethod
    def _ruta_zip_destino(ruta_archivo: str) -> str:
        return ruta_archivo if ruta_archivo.lower().endswith(".zip") else f"{ruta_archivo}.zip"

    @staticmethod
    def _tiene_permiso_escritura(ruta_directorio: str) -> bool:
        return os.access(ruta_directorio, os.W_OK)

    async def _seleccionar_ruta_zip_destino(self) -> str | None:
        fp = ft.FilePicker()
        return await fp.save_file(
            allowed_extensions=["zip"],
            dialog_title="Guardar copia de seguridad",
            file_name=f"copia_{PERIODO}.zip",
        )

    async def _seleccionar_archivo_zip_origen(self) -> str | None:
        fp = ft.FilePicker()
        archivos = await fp.pick_files(
            allow_multiple=False,
            allowed_extensions=["zip"],
            dialog_title="Seleccionar copia para restaurar",
        )
        if not archivos:
            return None
        return archivos[0].path

    def _crear_zip(self, destino: str, rutas_incluidas: list[str]) -> tuple[int, list[str]]:
        agregados = 0
        omitidos = []
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zipf:
            for ruta in rutas_incluidas:
                nombre = os.path.basename(ruta)
                if not os.path.exists(ruta):
                    omitidos.append(nombre)
                    continue
                try:
                    zipf.write(ruta, arcname=nombre)
                    agregados += 1
                except PermissionError:
                    omitidos.append(f"{nombre} (sin permisos)")
                except IOError as err:
                    omitidos.append(f"{nombre} (error E/S: {err})")
        return agregados, omitidos

    def _restaurar_zip(self, ruta_zip: str) -> tuple[int, list[str]]:
        restaurados = 0
        errores = []
        with zipfile.ZipFile(ruta_zip, "r") as zipf:
            for archivo in zipf.infolist():
                if archivo.is_dir():
                    continue
                destino = os.path.join(self._ruta_ex, archivo.filename)
                try:
                    with open(destino, "wb") as f:
                        f.write(zipf.read(archivo.filename))
                    restaurados += 1
                except Exception as err:
                    errores.append(f"{archivo.filename} (error: {err})")
        return restaurados, errores

    def generar_copia(self, e):
        self.checks_empresas.clear()
        empresas = self._empresas_uc.obtener_empresas(session.EMPRESA_ACTUAL["producto"])
        lista_checks = [self._crear_check_empresa(emp) for emp in empresas]
        self.checks_empresas.extend(lista_checks)

        lista_empresas = ft.Container(
            content=ft.Column(
                lista_checks,
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
                height=250,
            ),
            padding=15,
            border=ft.border.all(1, PINK_200),
            border_radius=8,
            bgcolor=PINK_50,
        )

        contenido = ft.Column(
            [
                ft.Text("Seleccione las empresas a incluir en la copia:", weight=ft.FontWeight.BOLD, size=14),
                lista_empresas,
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "Crear copia", 
                            on_click=self._crear_zip_con_seleccion, 
                            icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
                            style=BOTON_PRINCIPAL,
                        ),
                        ft.TextButton(
                            "Volver", 
                            on_click=self._volver_menu_principal, 
                            icon=ft.Icons.ARROW_BACK,
                            style=BOTON_SECUNDARIO_SIN
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_AROUND,
                )
            ],
            spacing=15,
        )

        self.contenedor_dinamico.controls = [contenido]
        self._ocultar_mensaje()
        self.page.update()

    async def _crear_zip_con_seleccion(self, e):
        rutas_incluidas = [chk.ruta_archivo for chk in self.checks_empresas if chk.value]
        if not rutas_incluidas:
            self._mostrar_mensaje("Debe seleccionar al menos una empresa.")
            return

        ruta_archivo = await self._seleccionar_ruta_zip_destino()
        if not ruta_archivo:
            return

        destino = self._ruta_zip_destino(ruta_archivo)
        directorio_destino = os.path.dirname(destino)
        if not self._tiene_permiso_escritura(directorio_destino):
            self._mostrar_mensaje(f"No tiene permisos de escritura en: {directorio_destino}")
            return

        try:
            agregados, omitidos = self._crear_zip(destino, rutas_incluidas)
            if agregados == 0:
                self._mostrar_mensaje("No se agregaron archivos a la copia.")
                return
            msg = f"Copia creada correctamente. Archivos incluidos: {agregados}."
            if omitidos:
                msg += f" Omitidos: {len(omitidos)}."
            self._mostrar_mensaje(msg)
        except Exception as err:
            self._mostrar_mensaje(f"Error al generar copia: {err}")

    async def restaurar_copia(self, e):
        zip_file = await self._seleccionar_archivo_zip_origen()
        if not zip_file:
            return
        if not os.path.exists(zip_file):
            self._mostrar_mensaje(f"El archivo ZIP no existe: {zip_file}")
            return
        if not self._tiene_permiso_escritura(self._ruta_ex):
            self._mostrar_mensaje(f"No tiene permisos de escritura en: {self._ruta_ex}")
            return

        try:
            restaurados, errores = self._restaurar_zip(zip_file)
            if restaurados == 0:
                self._mostrar_mensaje("No se restauraron archivos.")
                return
            msg = f"Restauración completada. Archivos restaurados: {restaurados}."
            if errores:
                msg += f" Con errores: {len(errores)}."
            self._mostrar_mensaje(msg)
        except Exception as err:
            self._mostrar_mensaje(f"Error al restaurar: {err}")

    def _volver_menu_principal(self, e):
        self._render_menu_principal(estilo_boton=BOTON_SECUNDARIO)

    # ---------------- Abrir ------------------
    def abrir(self):
        self._ruta_ex = self._helisa_uc.ruta_directorio_exogena()
        self.contenedor_dinamico.controls = self._menu_principal_controles(BOTON_PRINCIPAL)
        self._ocultar_mensaje()
        self.page.show_dialog(self.dialog)

    # ---------------- Cerrar ------------------
    def cerrar(self, e=None):
        self.page.pop_dialog()
        self.mensaje.visible = False
