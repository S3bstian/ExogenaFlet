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

    def generar_copia(self, e):
        # limpiar lista de checkboxes anteriores
        self.checks_empresas.clear()

        empresas = self._empresas_uc.obtener_empresas(session.EMPRESA_ACTUAL["producto"])

        lista_checks = []

        for emp in empresas:
            ruta = self._ruta_ex + r"\\HELI" + str(emp["codigo"]).zfill(2) + 'BD.EXG'
            chk = ft.Checkbox(
                label=f"{emp['codigo']} - {emp['nombre']}", 
                active_color=PINK_200,
                check_color=WHITE,
            )
            # propiedad personalizada para guardar la ruta
            chk.ruta_archivo = ruta
            self.checks_empresas.append(chk)
            lista_checks.append(chk)

        # Contenedor para la lista de empresas con scroll
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

        # reemplazamos SOLO el contenido dinámico (no movemos self.mensaje)
        self.contenedor_dinamico.controls = [contenido]
        self.mensaje.visible = False
        self.page.update()

    async def _crear_zip_con_seleccion(self, e):
        rutas_incluidas = [chk.ruta_archivo for chk in self.checks_empresas if chk.value]

        if not rutas_incluidas:
            self.mensaje.value = "Debe seleccionar al menos una empresa."
            self.mensaje.visible = True
            self.page.update()
            return

        async def guardar_zip_async():
            fp = ft.FilePicker()
            ruta_archivo = await fp.save_file(
                allowed_extensions=["zip"],
                dialog_title="Guardar copia de seguridad",
                file_name=f"copia_{PERIODO}.zip"
            )
            
            if not ruta_archivo:
                return
            
            destino = ruta_archivo
            if not destino.lower().endswith(".zip"):
                destino += ".zip"
            
            try:
                # Validar permisos de escritura
                directorio_destino = os.path.dirname(destino)
                if not os.access(directorio_destino, os.W_OK):
                    self.mensaje.value = f"No tiene permisos de escritura en: {directorio_destino}"
                    self.mensaje.visible = True
                    self.page.update()
                    return
                
                archivos_agregados = 0
                archivos_no_encontrados = []
                
                with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for ruta in rutas_incluidas:
                        if not os.path.exists(ruta):
                            archivos_no_encontrados.append(os.path.basename(ruta))
                            continue
                        
                        try:
                            zipf.write(ruta, arcname=os.path.basename(ruta))
                            archivos_agregados += 1
                        except PermissionError:
                            archivos_no_encontrados.append(f"{os.path.basename(ruta)} (sin permisos)")
                        except IOError as e:
                            archivos_no_encontrados.append(f"{os.path.basename(ruta)} (error E/S: {e})")

                self.mensaje.value = "Copia creada correctamente."
            except Exception as err:
                self.mensaje.value = f"Error al generar copia: {err}"

            self.mensaje.visible = True
            self.page.update()

        await guardar_zip_async()

    async def restaurar_copia(self, e):
        async def restaurar_async():
            fp = ft.FilePicker()
            archivos = await fp.pick_files(
                allow_multiple=False,
                allowed_extensions=["zip"],
                dialog_title="Seleccionar copia para restaurar"
            )
            
            if not archivos or len(archivos) == 0:
                return
            
            zip_file = archivos[0].path
            
            try:
                # Validar que el archivo ZIP existe
                if not os.path.exists(zip_file):
                    self.mensaje.value = f"El archivo ZIP no existe: {zip_file}"
                    self.mensaje.visible = True
                    self.page.update()
                    return
                
                # Validar permisos de escritura en el directorio de destino
                if not os.access(self._ruta_ex, os.W_OK):
                    self.mensaje.value = f"No tiene permisos de escritura en: {self._ruta_ex}"
                    self.mensaje.visible = True
                    self.page.update()
                    return
                
                archivos_restaurados = 0
                archivos_error = []
                
                with zipfile.ZipFile(zip_file, 'r') as zipf:
                    for archivo in zipf.infolist():
                        if archivo.is_dir():
                            continue
                        
                        destino = os.path.join(self._ruta_ex, archivo.filename)
                        
                        try:
                            with open(destino, 'wb') as f:
                                f.write(zipf.read(archivo.filename))
                            archivos_restaurados += 1
                        except Exception as e:
                            archivos_error.append(f"{archivo.filename} (error: {e})")

                self.mensaje.value = "Restauración completada"
            except Exception as err:
                self.mensaje.value = f"Error al restaurar: {err}"

            self.mensaje.visible = True
            self.page.update()

        await restaurar_async()

    def _volver_menu_principal(self, e):
        self.contenedor_dinamico.controls = [
            ft.ElevatedButton(
                "Generar copia", 
                on_click=self.generar_copia, 
                icon=ft.Icons.BACKUP_OUTLINED, 
                style=BOTON_SECUNDARIO,
                width=250,
                height=60,
            ),
            ft.ElevatedButton(
                "Restaurar copia", 
                on_click=self.restaurar_copia, 
                icon=ft.Icons.RESTORE_OUTLINED, 
                style=BOTON_SECUNDARIO,
                width=250,
                height=60,
            )
        ]
        self.page.update()

    # ---------------- Abrir ------------------
    def abrir(self):
        self._ruta_ex = self._helisa_uc.ruta_directorio_exogena()
        self.contenedor_dinamico.controls = [
            ft.ElevatedButton(
                "Generar copia", 
                on_click=self.generar_copia, 
                icon=ft.Icons.BACKUP_OUTLINED, 
                style=BOTON_PRINCIPAL,
                width=250,
                height=60,
            ),
            ft.ElevatedButton(
                "Restaurar copia", 
                on_click=self.restaurar_copia, 
                icon=ft.Icons.RESTORE_OUTLINED, 
                style=BOTON_PRINCIPAL,
                width=250,
                height=60,
            )
        ]
        self.mensaje.visible = False
        self.page.show_dialog(self.dialog)

    # ---------------- Cerrar ------------------
    def cerrar(self, e=None):
        self.page.pop_dialog()
        self.mensaje.visible = False
