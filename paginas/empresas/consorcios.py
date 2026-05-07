import flet as ft
from core import session
from ui.colors import PINK_200, PINK_400
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO_SIN
from ui.dropdowns import DropdownCompact
from ui.snackbars import actualizar_mensaje_en_control
from utils.validators import aplicar_validacion_error_text, set_campo_error, validar_numero
from paginas.empresas.terceros import TercerosDialog


_COLUMNAS_TABLA_CONSORCIOS = [
    "Identidad",
    "Nombre",
    "Tipo ID",
    "Fidecomiso",
    "Porcentaje",
    "Tipo de Contrato",
    "Acción",
]


class ConsorciosDialog:
    def __init__(self, page, container):
        self.page = page
        self._consorcios_uc = container.consorcios_uc
        self._auth_uc = container.auth_uc
        self.consorcios_data, self.consorcios_originales = [], []
        self.empresa_actual, self.consorcios_activos = None, False
        self._cancelar_confirmado, self._table, self._field_refs = False, None, []
        self.terceros_dialog = TercerosDialog(page, self, container=container)
        self.tipos_contrato = [
            "Consorcio y/o unión temporal",
            "Exploración y explotación de hidrocarburos, gases y minerales",
            "Joint venture",
            "Cuentas en participación",
            "Convenios de cooperación con entidades públicas",
        ]
        self.mensaje = ft.Text("", size=14, color=ft.Colors.RED, italic=True, visible=False)

    def limpiar_mensaje(self):
        """Oculta cualquier mensaje mostrado en pantalla."""
        self.mensaje.visible = False
        dlg = getattr(self, "dialog_consorcios", None)
        if dlg:
            dlg.update()

    def _normalize(self, consorcio):
        """Convierte un registro de consorcio a un formato estandarizado para comparación."""
        return {
            "identidad": str(consorcio.get("identidad", "")).strip(),
            "razonsocial": str(consorcio.get("razonsocial", "")).strip(),
            "tipodocumento": str(consorcio.get("tipodocumento", "")).strip(),
            "fidecomiso": int(consorcio.get("fidecomiso") or 0),
            "porcentaje": float(consorcio.get("porcentaje") or 0),
            "tipo_contrato": str(consorcio.get("tipo_contrato", "")).strip(),
        }

    def _mapas_por_id_normalizado(self):
        """Índices id → registro normalizado para originales y datos actuales."""
        originales_por_id = {c["id"]: self._normalize(c) for c in self.consorcios_originales if c.get("id")}
        actuales_por_id = {c["id"]: self._normalize(c) for c in self.consorcios_data if c.get("id")}
        return originales_por_id, actuales_por_id

    def hay_cambios(self):
        """
        Detecta si existen cambios en los consorcios frente al estado original.
        Revisa nuevos sin ID, eliminados y campos distintos en existentes.
        """
        originales_por_id, actuales_por_id = self._mapas_por_id_normalizado()

        if any("id" not in c or not c.get("id") for c in self.consorcios_data):
            return True

        if set(originales_por_id.keys()) != set(actuales_por_id.keys()):
            return True

        return any(originales_por_id[cid] != actuales_por_id.get(cid) for cid in originales_por_id)

    def _switch_activar_consorcios(self) -> ft.Switch:
        return ft.Switch(
            value=self.consorcios_activos,
            label="Activar consorcios",
            active_track_color=PINK_200,
            on_change=self.toggle_consorcios,
        )

    def _panel_mensaje_desactivado(self) -> ft.Container:
        return ft.Container(
            content=ft.Text("Consorcios desactivados.", color=ft.Colors.GREY_600, italic=True),
            padding=10,
            visible=not self.consorcios_activos,
        )

    def open_consorcios_dialog(self):
        """Abre el diálogo de gestión de consorcios para la empresa dada."""
        self.empresa_actual, self._cancelar_confirmado = session.EMPRESA_ACTUAL, False
        self.mensaje.visible, self._table, self._field_refs = False, None, []

        self.consorcios_activos = self._consorcios_uc.verificar_consorcio_activo(self.empresa_actual["identidad"])
        self.consorcios_data = self._consorcios_uc.obtener_consorcios() or []
        self.consorcios_originales = [c.copy() for c in self.consorcios_data]

        switch = self._switch_activar_consorcios()
        self.mensaje_desactivado = self._panel_mensaje_desactivado()

        self.contenido_activado = ft.Container(
            content=self.build_tabla_consorcios(True),
            visible=self.consorcios_activos,
        )

        self.boton_agregar = ft.ElevatedButton(
            "Agregar Consorcio",
            icon=ft.Icons.ADD,
            on_click=self._abrir_dialogo_terceros,
            visible=self.consorcios_activos,
            style=BOTON_PRINCIPAL,
        )

        contenido = ft.Column(
            [
                switch,
                self.mensaje_desactivado,
                self.mensaje,
                self.contenido_activado,
                self.boton_agregar,
            ]
        )

        nombre_empresa = self.empresa_actual.get("nombre", "") if self.empresa_actual else ""
        self.dialog_consorcios = ft.AlertDialog(
            title=ft.Text(f"Gestión de Consorcios • {nombre_empresa}", text_align=ft.TextAlign.CENTER),
            content=contenido,
            bgcolor=ft.Colors.WHITE,
            modal=True,
            elevation=15,
            shape=ft.RoundedRectangleBorder(radius=12),
            actions=[
                ft.TextButton(
                    content="Cancelar",
                    on_click=lambda _e: self.cancelar_dialogo(),
                    style=BOTON_SECUNDARIO_SIN,
                ),
                ft.Button(content="Guardar", on_click=lambda _e: self.guardar_consorcios(), style=BOTON_PRINCIPAL),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(self.dialog_consorcios)

    def cancelar_dialogo(self):
        """
        Cierre en dos pasos: si hay cambios, el primer clic muestra advertencia;
        si el usuario insiste, cierra el diálogo. Si no hay cambios, cierra directo.
        """
        if self.hay_cambios():
            if self._cancelar_confirmado:
                self.page.pop_dialog()
            else:
                self._cancelar_confirmado = True
                actualizar_mensaje_en_control(
                    "Cambios sin guardar. Cancela de nuevo para salir.",
                    self.mensaje,
                    ft.Colors.ORANGE,
                )
        else:
            self.page.pop_dialog()

    def toggle_consorcios(self, e):
        """Activa o desactiva consorcios y actualiza base de datos y UI."""
        self.consorcios_activos = e.control.value
        self._auth_uc.actualizar_activo(
            "Empresas",
            "ConsorciosActivo",
            "Identidad",
            self.empresa_actual["identidad"],
            self.consorcios_activos,
            -1,
        )
        self.mensaje_desactivado.visible = not self.consorcios_activos
        self.contenido_activado.visible = self.consorcios_activos
        self.boton_agregar.visible = self.consorcios_activos

        if self.consorcios_activos:
            self.contenido_activado.content, self._table = self.build_tabla_consorcios(True), None

        self.dialog_consorcios.update()

    def _controles_fila_consorcio(self, index: int, consorcio: dict):
        fidecomiso_field = ft.TextField(
            value=str(consorcio.get("fidecomiso", "")),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=60,
        )
        porcentaje_field = ft.TextField(
            value=str(consorcio.get("porcentaje", "")),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=60,
        )
        tipo_contrato_field = DropdownCompact(
            value=consorcio.get("tipo_contrato", ""),
            options=[ft.DropdownOption(key=t, text=t) for t in self.tipos_contrato],
            width=200,
        )

        fidecomiso_field.on_change = lambda e, idx=index, ctrl=fidecomiso_field: self.actualizar_campo(
            idx, "fidecomiso", e.control.value, ctrl
        )
        porcentaje_field.on_change = lambda e, idx=index, ctrl=porcentaje_field: self.actualizar_campo(
            idx, "porcentaje", e.control.value, ctrl
        )
        tipo_contrato_field.on_select = lambda e, idx=index: self.actualizar_campo(
            idx, "tipo_contrato", e.control.value, None
        )

        self._field_refs.append((fidecomiso_field, porcentaje_field, tipo_contrato_field))

        return (
            ft.DataCell(ft.Text(consorcio.get("identidad", ""), width=71)),
            ft.DataCell(ft.Text(consorcio.get("razonsocial", ""), expand=True)),
            ft.DataCell(ft.Text(consorcio.get("tipodocumento", ""))),
            ft.DataCell(fidecomiso_field),
            ft.DataCell(porcentaje_field),
            ft.DataCell(tipo_contrato_field),
            ft.DataCell(
                ft.IconButton(
                    icon=ft.Icons.DELETE,
                    tooltip="Eliminar consorcio",
                    style=BOTON_SECUNDARIO_SIN,
                    on_click=lambda _e, idx=index: self.quitar_consorcio(idx),
                    icon_color=PINK_400,
                )
            ),
        )

    def _tabla_vacia_placeholder(self):
        return ft.Column(
            [
                ft.Divider(),
                ft.Text("No se han agregado consorcios.", color=ft.Colors.GREY_500),
                ft.Divider(),
            ]
        )

    def build_tabla_consorcios(self, rebuild=False):
        """
        Construye la tabla de consorcios con campos editables.
        Usa caché (_table) para no reconstruir en cada cambio de tecla.
        """
        if self._table and not rebuild:
            return self._table

        if not self.consorcios_data:
            self._table = self._tabla_vacia_placeholder()
            return self._table

        filas, self._field_refs = [], []

        for index, consorcio in enumerate(self.consorcios_data):
            celdas = self._controles_fila_consorcio(index, consorcio)
            filas.append(ft.DataRow(cells=list(celdas)))

        self._table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(col)) for col in _COLUMNAS_TABLA_CONSORCIOS],
            rows=filas,
        )
        return self._table

    def actualizar_campo(self, index, campo, valor, control):
        """Valida y actualiza un campo editable en consorcios_data."""
        if not (0 <= index < len(self.consorcios_data)):
            return

        if campo == "porcentaje":
            es_valido = aplicar_validacion_error_text(
                control, valor, validar_numero, tipo="float", min_val=0, max_val=100
            )
            if es_valido:
                self.consorcios_data[index][campo] = float(valor) if valor else 0.0
            else:
                actualizar_mensaje_en_control("Porcentaje inválido (debe ser entre 0 y 100)", self.mensaje)
                return

        elif campo == "fidecomiso":
            if valor == "":
                self.consorcios_data[index][campo] = 0
                if control:
                    set_campo_error(control, None)
            else:
                es_valido = aplicar_validacion_error_text(
                    control, valor, validar_numero, tipo="int", min_val=0
                )
                if es_valido:
                    self.consorcios_data[index][campo] = int(valor)
                else:
                    actualizar_mensaje_en_control("Fidecomiso inválido (debe ser numérico)", self.mensaje)
                    return
        else:
            self.consorcios_data[index][campo] = valor

        self.limpiar_mensaje()
        self.dialog_consorcios.update()

    def quitar_consorcio(self, index):
        """Elimina un consorcio de la lista y reconstruye la tabla."""
        if 0 <= index < len(self.consorcios_data):
            self.consorcios_data.pop(index)

        self._table = None
        self.contenido_activado.content = self.build_tabla_consorcios(True)
        self.contenido_activado.update()
        self.dialog_consorcios.update()

    def _validar_suma_porcentajes(self) -> bool:
        if not self.consorcios_data:
            return True
        try:
            total_porcentaje = sum(float(c.get("porcentaje") or 0) for c in self.consorcios_data)
        except (TypeError, ValueError):
            actualizar_mensaje_en_control("Hay porcentajes inválidos.", self.mensaje)
            return False

        if abs(total_porcentaje - 100.0) >= 0.01:
            actualizar_mensaje_en_control(
                f"El porcentaje total debe ser 100%. Actual: {total_porcentaje:.2f}%",
                self.mensaje,
            )
            return False
        return True

    def _diff_para_persistencia(self):
        """Listas eliminados, nuevos y actualizados respecto al snapshot original."""
        originales_por_id, actuales_por_id = self._mapas_por_id_normalizado()

        eliminados_ids = [cid for cid in originales_por_id if cid not in actuales_por_id]
        nuevos_registros = [c for c in self.consorcios_data if not c.get("id")]
        actualizados_registros = [
            consorcio
            for cid, valores_original in originales_por_id.items()
            if cid in actuales_por_id and valores_original != actuales_por_id[cid]
            for consorcio in self.consorcios_data
            if consorcio.get("id") == cid
        ]
        return eliminados_ids, nuevos_registros, actualizados_registros

    def _persistir_cambios_consorcios(self, eliminados_ids, nuevos_registros, actualizados_registros) -> list[str]:
        errores = []
        for cid in eliminados_ids:
            if not self._consorcios_uc.eliminar_consorcio(cid):
                errores.append(f"No se eliminó Id {cid}")

        for nuevo in nuevos_registros:
            try:
                nuevo["id"] = self._consorcios_uc.crear_consorcio(nuevo) or None
            except Exception as e:
                errores.append(f"Error insertando {nuevo.get('identidad')}: {e}")

        for actualizado in actualizados_registros:
            try:
                if not self._consorcios_uc.actualizar_consorcio(actualizado):
                    errores.append(f"No se actualizó Id {actualizado.get('id')}")
            except Exception as e:
                errores.append(f"Error actualizando {actualizado.get('id')}: {e}")

        return errores

    def guardar_consorcios(self):
        """
        Sincroniza los consorcios con la base de datos:
        valida 100% de porcentajes, detecta eliminados/nuevos/actualizados y persiste.
        """
        if not self._validar_suma_porcentajes():
            return

        eliminados_ids, nuevos_registros, actualizados_registros = self._diff_para_persistencia()
        errores = self._persistir_cambios_consorcios(eliminados_ids, nuevos_registros, actualizados_registros)

        if errores:
            actualizar_mensaje_en_control("Errores: " + "; ".join(errores), self.mensaje)
            return

        self.consorcios_originales = self._consorcios_uc.obtener_consorcios() or []
        self.consorcios_data = [c.copy() for c in self.consorcios_originales]

        self.page.pop_dialog()
        actualizar_mensaje_en_control("Consorcios guardados correctamente", self.mensaje, ft.Colors.GREEN)

    def _abrir_dialogo_terceros(self, e):
        """
        Cierra el diálogo de consorcios y abre el catálogo de terceros para
        seleccionar integrantes del consorcio.
        """
        if getattr(self, "boton_agregar", None):
            self.boton_agregar.disabled = True
            self.page.update()

        loop = self.page.session.connection.loop

        def _abrir():
            if getattr(self, "dialog_consorcios", None):
                self.page.pop_dialog()
                self.page.update()
            self.terceros_dialog.open_agregar_dialog()

        loop.call_later(0.05, _abrir)
