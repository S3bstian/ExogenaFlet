from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from application.use_cases.formatos_conceptos.gestion_formatos_ui import (
        GestionFormatosUIUseCase,
    )

from ui.colors import PINK_50, PINK_200, PINK_400
from ui.buttons import BOTON_LISTA, BOTON_SUBLISTA, BOTON_PRINCIPAL, BOTON_SECUNDARIO_SIN
from ui.progress import crear_loader_row, SIZE_SMALL
from paginas.modulopasos.formatos_conceptos.atributos_dialog import AtributosDialog
from ui.snackbars import mostrar_mensaje_overlay
from utils.ui_sync import ejecutar_en_ui, loader_row_fin, loader_row_trabajo, loader_row_visibilidad

class FormatosPage(ft.Column):
    def __init__(self, page, app):
        super().__init__()
        self._page = page
        self._app = app
        container = app.container
        self._formatos_uc = container.formatos_uc
        self.expand = True
        self.submenus = {}
        self.dialog = None
        self.atributos_dialog = AtributosDialog(self._page, self, container)
        self._listview = ft.ListView(expand=True, spacing=5, padding=10, controls=[])
        self.loader = crear_loader_row("Cargando formatos...", size=SIZE_SMALL)
        self.loader.visible = False
        # Se asigna al abrir el diálogo de estructura (`_mostrar_dialog_estructura`).
        self.loader_estructura_inline = None
        self.tipogprev = None

    @property
    def formatos_uc(self) -> GestionFormatosUIUseCase:
        """Expuesto para `AtributosDialog` sin acoplar a `_formatos_uc` interno."""
        return self._formatos_uc

    # ====================================================
    # MENÚ PRINCIPAL
    # ====================================================
    def formato_menu(self, formato):
        nombre = formato[1]
        descripcion = formato[2]

        submenu = ft.Column(
            visible=False,
            spacing=-10,
            controls=[
                ft.Text(
                    "           Conceptos del formato:\n           ━━━━━━━━━━━━━━━━━━━━━━━━━━",
                    size=12,
                    weight=ft.FontWeight.BOLD
                )
            ],
        )

        btn = ft.TextButton(
            content=f"{nombre} - {descripcion}",
            style=BOTON_LISTA,
            on_click=lambda e: self.toggle_formato(nombre, formato),
        )

        self.submenus[nombre] = submenu
        return ft.Column([ft.Row([btn]), submenu])

    def _set_loader_overlay(self, visible: bool) -> None:
        """Muestra/oculta loader overlay global cuando el app lo soporta."""
        if hasattr(self._app, "_loader_overlay_mostrar"):
            self._app._loader_overlay_mostrar(visible)

    def _cargar_conceptos_formato(self, nombre: str):
        """Obtiene conceptos asociados al formato seleccionado."""
        return self._formatos_uc.obtener_conceptos(0, 1000, nombre)

    def _poblar_submenu_conceptos(self, submenu: ft.Column, nombre: str, formato, conceptos: list) -> None:
        """Reconstruye opciones de concepto en el submenú del formato."""
        titulo = submenu.controls[0]
        submenu.controls = [titulo]
        for concepto in conceptos:
            submenu.controls.append(
                ft.TextButton(
                    content=ft.Text(
                        f"{concepto['codigo']} - {concepto['descripcion']}",
                        no_wrap=False,
                    ),
                    style=BOTON_SUBLISTA,
                    on_click=lambda e, concepto_actual=concepto: self.open_estructura(
                        formato, concepto_actual
                    ),
                    margin=ft.margin.only(left=55, top=5),
                )
            )
        self._toggle_submenu_visible(nombre, submenu)
        submenu.update()
        self._page.update()

    def _toggle_submenu_visible(self, nombre: str, submenu: ft.Column) -> None:
        """Alterna visibilidad del submenú objetivo y colapsa los demás."""
        for nombre_menu, submenu_menu in self.submenus.items():
            submenu_menu.visible = nombre_menu == nombre and not submenu.visible

    def _mostrar_error_carga_conceptos(self, ex: Exception) -> None:
        """Muestra error de carga de conceptos con overlay finalizado."""
        self._set_loader_overlay(False)
        mostrar_mensaje_overlay(self._page, f"Error al cargar conceptos: {ex}", 5000)

    def _on_conceptos_formato_cargados(self, nombre: str, formato, submenu: ft.Column, conceptos: list) -> None:
        """Actualiza UI al terminar carga de conceptos por formato."""
        self._set_loader_overlay(False)
        if not conceptos:
            self.open_estructura(formato)
            return
        self._poblar_submenu_conceptos(submenu, nombre, formato, conceptos)

    def _ejecutar_en_hilo(self, trabajo, on_success=None, on_error=None) -> None:
        """Ejecuta trabajo en background y delega callbacks de éxito/error en UI thread."""
        def _worker():
            try:
                resultado = trabajo()
            except Exception as ex:
                if on_error:
                    ejecutar_en_ui(self._page, lambda ex=ex: on_error(ex))
                return
            if on_success:
                ejecutar_en_ui(self._page, lambda resultado=resultado: on_success(resultado))
        self._page.run_thread(_worker)

    def toggle_formato(self, nombre, formato):
        submenu = self.submenus[nombre]
        # Evita saltos de scroll: el loader visual para conceptos se muestra en overlay.
        self._set_loader_overlay(True)
        self._ejecutar_en_hilo(
            trabajo=lambda: self._cargar_conceptos_formato(nombre),
            on_success=lambda resultado: self._on_conceptos_formato_cargados(
                nombre,
                formato,
                submenu,
                resultado[0] if resultado else [],
            ),
            on_error=self._mostrar_error_carga_conceptos,
        )

    # ====================================================
    # VISTA PRINCIPAL
    # ====================================================
    def view(self):
        return ft.Container(
            expand=True,
            alignment=ft.Alignment(0, -1),
            content=ft.Column(
                [
                    ft.Text("Formatos disponibles:", size=22, weight=ft.FontWeight.BOLD),
                    self.loader,
                    ft.Container(expand=True, content=self._listview),
                ],
                expand=True,
            ),
        )

    def actualizar_formatos(self):
        """Carga get_formatos en segundo plano y actualiza el ListView. Llamar desde on_enter."""
        loader_row_visibilidad(self._page, self.loader, True)
        self._ejecutar_en_hilo(
            trabajo=self._formatos_uc.obtener_formatos,
            on_success=self._on_formatos_cargados,
            on_error=self._on_error_actualizar_formatos,
        )

    def _on_formatos_cargados(self, formatos: list) -> None:
        """Pinta listado de formatos una vez completada la consulta."""
        self._listview.controls = [self.formato_menu(formato) for formato in formatos]
        loader_row_fin(self._page, self.loader)
        self._page.update()

    def _on_error_actualizar_formatos(self, e: Exception) -> None:
        """Muestra error de consulta al cargar listado principal de formatos."""
        loader_row_fin(self._page, self.loader)
        mostrar_mensaje_overlay(self._page, f"Error cargando formatos: {e}", 5555)

    # ====================================================
    # DIÁLOGO ESTRUCTURA
    # ====================================================
    def _cargar_datos_estructura(self, formato, concepto):
        """Lee elementos y atributos desde BD (llamar desde hilo de trabajo)."""
        estructura = {"mas": {}}
        formato_el = 0
        for elem_id, etiqueta, formato_el, idconcepto, tglobal in self._formatos_uc.obtener_elementos(
            concepto["id"] if concepto else None,
            None if concepto else formato[0],
        ):
            atributos = [
                {
                    "Id": a_id,
                    "Nombre": nm,
                    "Descripcion": ds or "",
                    "Clase": cl,
                    "Tipo": tipoac,
                }
                for a_id, nm, ds, cl, tipoac in self._formatos_uc.obtener_atributos(elem_id)
            ]

            estructura["mas"][etiqueta] = {
                "elem_id": elem_id,
                "tglobal": tglobal,
                "atributos": atributos,
            }

        return estructura, formato_el

    def open_estructura(self, formato, concepto=None):
        loader_row_trabajo(self._page, self.loader, None, "Cargando estructura...")
        self._ejecutar_en_hilo(
            trabajo=lambda: self._cargar_datos_estructura(formato, concepto),
            on_success=lambda datos: self._on_estructura_cargada(formato, concepto, datos),
            on_error=self._on_error_open_estructura,
        )

    def _on_estructura_cargada(self, formato, concepto, datos: tuple) -> None:
        """Finaliza carga de estructura y abre diálogo con los datos obtenidos."""
        estructura, formato_el = datos
        loader_row_fin(self._page, self.loader)
        self._mostrar_dialog_estructura(formato, concepto, estructura, formato_el)

    def _on_error_open_estructura(self, ex: Exception) -> None:
        """Muestra error al cargar estructura de formato/concepto."""
        loader_row_fin(self._page, self.loader)
        mostrar_mensaje_overlay(self._page, f"Error al cargar la estructura: {ex}", 5000)

    def _mostrar_dialog_estructura(self, formato, concepto, estructura, formato_el):
        submenus = {}

        # ----------------------------------------------------
        # CREAR NODO
        # ----------------------------------------------------
        def crear_nodo(nombre, info, nivel=1):
            atributos = info["atributos"]
            # Altura uniforme + alineación vertical en celdas (evita texto pegado a los divisores).
            attr_row_h = 40

            def data_cell(control, x=-1):
                return ft.DataCell(
                    ft.Container(
                        content=control,
                        alignment=ft.Alignment(x, 0),
                        height=attr_row_h,
                    )
                )

            # tabla atributos
            rows = []
            for atributo in atributos:
                # Regla de negocio: CLASE=3 no tiene configuración por opciones.
                clase_attr = atributo.get("Clase")
                try:
                    clase_attr = int(clase_attr) if clase_attr is not None and str(clase_attr).strip() != "" else None
                except (TypeError, ValueError):
                    clase_attr = None
                # En CLASE=2 también se permite configurar (DATOSESPECIFICOS).
                if clase_attr != 3 and (clase_attr == 2 or atributo["Tipo"] < 1000):
                    rows.append(
                        ft.DataRow(
                            cells=[
                                data_cell(ft.Text(atributo["Nombre"])),
                                data_cell(
                                    ft.Row(
                                        [
                                            ft.Text(atributo["Descripcion"]),
                                            ft.IconButton(
                                                icon=ft.Icons.EDIT_NOTE,
                                                tooltip="Opciones",
                                                style=BOTON_SECUNDARIO_SIN,
                                                on_click=lambda e, atributo_actual=atributo:
                                                    self.atributos_dialog.open_opciones_dialog(
                                                        formato, atributo_actual, concepto, info["tglobal"]
                                                    ),
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                ),
                            ]
                        )
                    )
                else:
                    rows.append(
                        ft.DataRow(
                            cells=[
                                data_cell(ft.Text(atributo["Nombre"])),
                                data_cell(ft.Text(atributo["Descripcion"])),
                            ]
                        )
                    )

            tabla = ft.DataTable(
                columns=[ft.DataColumn(ft.Text("Nombre")), ft.DataColumn(ft.Text("Descripción"))],
                rows=rows,
                column_spacing=10,
                data_row_min_height=attr_row_h,
                data_row_max_height=attr_row_h,
                heading_row_height=30,
                heading_row_color=PINK_50,
                divider_thickness=0.5,
            )

            # -------------------
            # SegmentButton
            # -------------------
            if nombre != "Cab" and nombre != "cab":
                tglobal = info.get("tglobal") if info.get("tglobal") in ["T", "C", "B", "A"] else "T"
                self.tipogprev = tglobal
                seg_ref = type("SegRef", (), {"data": info, "selected": tglobal, "buttons": []})()
                opciones = [("T", "Terceros"), ("C", "Cuentas"), ("B", "Bancos"), ("A", "Activos")]

                def _on_tipo_click(e, ref, val):
                    class FakeE:
                        data = f'["{val}"]'
                    self.confirmar_cambio_tipo(FakeE(), ref)

                for val, label in opciones:
                    btn = ft.TextButton(
                        content=label,
                        data=val,
                        style=BOTON_PRINCIPAL if val == tglobal else BOTON_SECUNDARIO_SIN,
                        on_click=lambda e, ref=seg_ref, v=val: _on_tipo_click(e, ref, v),
                    )
                    seg_ref.buttons.append(btn)
                # Borde que reemplaza el del SegmentedButton
                seg = ft.Container(
                    content=ft.Row(seg_ref.buttons, spacing=4),
                    border=ft.border.all(1, PINK_200),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=6, vertical=2),
                )
                label_tipo = ft.Text("Tipo acumulado:", size=14, weight="bold")
            else:
                seg = ft.Text("", size=14)
                label_tipo = ft.Text("", size=14)
            fila = ft.Row(
                [
                    ft.TextButton(
                        f"<{nombre}>",
                        style=BOTON_LISTA,
                        on_click=lambda e: toggle_submenu(nombre)
                    ),
                    label_tipo,
                    seg,
                ],
                alignment="spaceBetween"
            )

            contenido = ft.Container(
                visible=False,
                padding=ft.padding.only(left=15 * nivel, top=3),
                border=ft.border.only(left=ft.border.BorderSide(1, ft.Colors.GREY_300)),
                content=tabla
            )

            cierre = ft.Text(f"</{nombre}>", visible=False, color=ft.Colors.GREY_600)

            submenus[nombre] = (contenido, cierre)
            return ft.Column([fila, contenido, cierre], spacing=3)

        # ----------------------------------------------------
        # Alternar submenús
        # ----------------------------------------------------
        def toggle_submenu(nombre):
            for k, (sub, cierre) in submenus.items():
                sub.visible = cierre.visible = (k == nombre and not sub.visible)
            self.dialog.update()

        # panel principal
        hijos = [
            crear_nodo(nombre, info, nivel=1)
            for nombre, info in estructura["mas"].items()
        ]

        self._panel_principal = ft.Column(
            [
                ft.Text("<mas>", size=15, weight=ft.FontWeight.BOLD, color=PINK_400),
                *hijos,
                ft.Text("</mas>", size=15, weight=ft.FontWeight.BOLD, color=PINK_400),
            ],
            scroll=ft.ScrollMode.AUTO,
        )

        # Instancia nueva por apertura: evita controles huérfanos al cerrar/reabrir el diálogo.
        self.loader_estructura_inline = crear_loader_row("Cargando configuración...", size=SIZE_SMALL)
        self.loader_estructura_inline.visible = False

        # Stack: el Column del árbol define el tamaño del diálogo
        # La franja del loader va superpuesta arriba solo mientras `_loader_estructura_slot.visible`.
        self._loader_estructura_slot = ft.Container(
            content=self.loader_estructura_inline,
            bgcolor=ft.Colors.WHITE,
            padding=ft.padding.symmetric(vertical=6, horizontal=8),
            top=0,
            left=0,
            right=0,
            visible=False,
        )
        self._estructura_dialog_body = ft.Stack(
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            controls=[
                self._panel_principal,
                self._loader_estructura_slot,
            ],
        )

        # Diálogo principal (estructura). La confirmación se abre encima con show_dialog (apilado).
        self.dialog = ft.AlertDialog(
            title=ft.Text(f"Formato {formato_el} • Concepto {concepto['codigo']}" if concepto else "Formato " + str(formato_el)),
            content=self._estructura_dialog_body,
            bgcolor=ft.Colors.WHITE,
            elevation=15,
            modal=False,
            shape=ft.RoundedRectangleBorder(radius=12),
            actions=[
                ft.TextButton(
                    content="Cerrar",
                    on_click=lambda e: self._page.pop_dialog(),
                    style=BOTON_SECUNDARIO_SIN
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )

        self._page.show_dialog(self.dialog)
        self._page.update()

    # ====================================================
    # CAMBIO TIPO ACUMULADO (diálogo de confirmación apilado sobre el principal)
    # ====================================================
    def confirmar_cambio_tipo(self, e, seg):
        info = seg.data
        nuevo = e.data[2:-2]               

        self._pending_info = info
        self._pending_seg = seg
        self._pending_prev = self.tipogprev
        self._pending_new = nuevo

        # Diálogo de confirmación encima del principal (Flet 0.80 permite apilar)
        dialog_confirm = ft.AlertDialog(
            title=ft.Text("Confirmar cambio de tipo"),
            content=ft.Text(
                "Si cambia el tipo acumulado, se perderán las configuraciones "
                "de atributos de este elemento.\n\n¿Desea continuar?",
                size=14
            ),
            actions=[
                ft.TextButton(content="Cancelar", on_click=self._cancelar_cambio, style=BOTON_SECUNDARIO_SIN),
                ft.Button(content="Continuar", on_click=self._confirmar_cambio, style=BOTON_PRINCIPAL),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=True,
            bgcolor=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        self._page.show_dialog(dialog_confirm)

    def _cancelar_cambio(self, e):
        seg = self._pending_seg
        seg.selected = self._pending_prev
        self._actualizar_estilos_seg(seg)
        self._page.pop_dialog()  # cierra solo el diálogo de confirmación; el principal sigue abierto

    def _confirmar_cambio(self, e):
        seg = self._pending_seg
        info = self._pending_info
        self._formatos_uc.actualizar_tipo_global(info["elem_id"], self._pending_new)
        seg.selected = self._pending_new
        info["tglobal"] = self._pending_new
        self.tipogprev = info["tglobal"]
        self._actualizar_estilos_seg(seg)
        self._page.pop_dialog()  # cierra el diálogo de confirmación
        self._page.update()  # refresca el diálogo principal visible

    def _actualizar_estilos_seg(self, seg):
        """Actualiza estilos de los botones tipo acumulado (seg es seg_ref con .buttons)."""
        if hasattr(seg, "buttons"):
            for boton in seg.buttons:
                boton.style = (
                    BOTON_PRINCIPAL if boton.data == seg.selected else BOTON_SECUNDARIO_SIN
                )
