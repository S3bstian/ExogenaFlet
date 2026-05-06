import flet as ft
from core.catalogues import PAISES, TIPOSDOC, DEPARTAMENTOS, MUNICIPIOS, obtener_codigo_tipodoc, obtener_nombre_pais, obtener_nombre_tipodoc, obtener_nombre_departamento, obtener_nombre_municipio
from ui.colors import PINK_200, GREY_700, WHITE
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO, BOTON_SECUNDARIO_SIN
from ui.dropdowns import DropdownCompact
from ui.progress import crear_loader_row, SIZE_SMALL
from ui.snackbars import actualizar_mensaje_en_control
from utils.validators import (
    aplicar_validacion_error_text,
    set_campo_error,
    validar_campo_obligatorio,
    validar_email,
    validar_numero,
)
from paginas.empresas.terceros import TercerosDialog
from paginas.modulopasos.hoja_trabajo.hoja_tools_front import formatear_pesos
from paginas.modulopasos.cartilla_terceros.herramientas_tercero import TerceroDialog
from utils.ui_sync import loader_row_fin, loader_row_trabajo, loader_row_visibilidad


# def _label_sin_conjuncion_huerfana(label: str) -> str:
#     """
#     La etiqueta del TextField se envuelve al ancho del control; el salto puede separar
#     conjunciones de una letra (o, y, e) de la palabra siguiente. NBSP evita ese corte.
#     """
#     if not label:
#         return label
#     # (^|\s) evita look-behind de ancho variable. NBSP fuera del template (re.sub no acepta \u ahí).
#     _nbsp = "\u00a0"

#     def _repl(m: re.Match) -> str:
#         return m.group(1) + m.group(2) + _nbsp

#     return re.sub(r"(^|\s)([oOyYeE])\s+(?=\S)", _repl, label)


class TrabajoDialog:
    """
    Diálogo de hoja de trabajo. `abrir(modo=...)` recibe un string: "nuevo", "editar",
    "fideicomiso_masivo", "eliminar". El resto del código compara `self.modo` con esos valores.
    """
    # ==================== CONSTANTES Y CONFIGURACIÓN ====================
    
    MAPEO_TERCERO_ATRIBUTO = {
        "razonsocial": [["RAZÓN", "RAZON"], ["SOCIAL"]],
        "tipodocumento": [["TIPO"], ["DOCUMENTO"]],
        "digitoverificacion": [["DIGITO", "DÍGITO"], ["VERIFICACION", "VERIFICACIÓN"]],
        "identidad": [["IDENTIFICACION", "IDENTIFICACIÓN"], ["NUMERO", "NÚMERO"]],
        "primerapellido": [["PRIMER"], ["APELLIDO"]],
        "segundoapellido": [["SEGUNDO"], ["APELLIDO"]],
        "primernombre": [["PRIMER"], ["NOMBRE"]],
        "segundonombre": [["SEGUNDO", "OTROS"], ["NOMBRE", "NOMBRES"]],
        "direccion": [["DIRECCIÓN", "DIRECCION"]],
        "departamento": [["DEPARTAMENTO"]],
        "municipio": [["MUNICIPIO"]],
        "pais": [["PAÍS", "PAIS"]],
    }
    # ==================== ANCHOS DE CONTROLES EDITABLES ====================
    # Edita estos diccionarios para asignar ancho por atributo.
    # - EXACTO: prioridad alta (coincidencia exacta de la etiqueta del atributo).
    # - CONTIENE: prioridad media (todas las palabras del patrón deben existir en la etiqueta).
    # - DEFAULT: fallback para cualquier campo no configurado.
    ANCHO_CONTROL_DEFAULT = 208
    ANCHO_RAZON_SOCIAL = 472
    ANCHO_POR_ATRIBUTO_EXACTO: dict[str, int] = {
        # "Tipo de documento": 174,
        # "Número de Identificación": 210,
    }
    ANCHO_POR_ATRIBUTO_CONTIENE: dict[tuple[str, ...], int] = {}
    
    def __init__(self, page, parent):
        self.page = page
        self.parent = parent
        
        # Estado del diálogo
        self.id_concepto = None
        self.identidad = None
        self.concepto = None
        self.datos = {}
        self.modo = "editar"
        self.tercero_actual = None
        self.atributos_info = {}
        self.atributos_clase = {}  # descripcion -> CLASE (ATRIBUTOS.CLASE)
        self.atributos_nombre = {}  # descripcion -> NOMBRE (ATRIBUTOS.NOMBRE)
        self.atributos_id = {}  # descripcion -> ID (ATRIBUTOS.ID)
        self.formato = ""
        
        # Controles UI
        self.campos = {}
        self.mensaje = ft.Text("", size=14, italic=True, visible=False)
        self.drop_dep = None
        self.drop_mun = None
        self.dialog = None
        self.dialog_trabajo_guardado = None
        self.filtro_tipo_actual = None
        self.filtro_subtipo_actual = None
        self.loader_fideicomiso = crear_loader_row("Aplicando cambios masivos...", size=SIZE_SMALL)
        self.loader_fideicomiso.visible = False
        self.loader_apertura_tercero = crear_loader_row("Abriendo selector de terceros...", size=SIZE_SMALL)
        self.loader_apertura_tercero.visible = False
        self._btn_confirmar_dialogo = None
        self._btn_selector_tercero = None
        self._btn_editar_tercero = None
        # Catálogo clase 2 -> clave padre en self.datos (resuelto vía HIJOS en BD).
        self._cache_padre_catalogo: dict[str, str | None] = {}

        c = parent._app.container
        self._terceros_uc = c.terceros_cartilla_uc
        self._formatos_uc = parent._formatos_ui_uc
        self._datos_uc = c.datos_especificos_uc

        # Diálogos externos
        self.tercero_dialog = TercerosDialog(
            page,
            consorcios_dialog=None,
            trabajo_dialog=self,
            modo_seleccion_unica=True,
            container=c,
        )
        self.tercero_dialog_editar = TerceroDialog(page, parent=self)

    def _mutar_hoja(self):
        """Caso de uso de mutaciones expuesto por `HojaTrabajoPage` (misma instancia que consultas)."""
        return self.parent._mutar_hoja_uc

    # ==================== MÉTODOS PÚBLICOS ====================
    
    def abrir(self, id_concepto=None, identidad=None, datos=None, concepto=None, modo=None):
        """
        Abre el diálogo en el modo indicado.
        - nuevo   : construye un formulario vacío (con opción para seleccionar tercero).
        - editar  : carga tercero actual y construye formulario con valores existentes.
        - eliminar: abre el diálogo específico de eliminación.
        """
        self.id_concepto = id_concepto
        self.identidad = identidad
        self.concepto = concepto
        self.datos = datos or {}
        self.modo = modo or "editar"

        if self.modo == "eliminar":
            self._abrir_dialogo_eliminar()
            return

        if self.modo != "editar":
            self.tercero_actual = None
            self.formato = ""

        if self.modo == "editar":
            self._cargar_tercero_actual()

        self._build_dialogo_formulario()
    
    def cerrar(self, e=None):
        """Cierra el diálogo y limpia el estado."""
        if self.dialog:
            self.page.pop_dialog()
        self.mensaje.visible = False
        self.dialog_trabajo_guardado = None
        self.dialog = None
        self.campos = {}
        self.drop_dep = None
        self.drop_mun = None
        self.filtro_tipo_actual = None
        self.filtro_subtipo_actual = None
        loader_row_fin(self.page, self.loader_fideicomiso)
        loader_row_fin(self.page, self.loader_apertura_tercero)
        self._btn_confirmar_dialogo = None

    def actualizar_tercero_editado(self):
        """Actualiza la tarjeta después de editar el tercero."""
        # Cerrar el diálogo guardado si existe
        if self.dialog_trabajo_guardado:
            self.page.pop_dialog()
            self.dialog_trabajo_guardado = None
        
        # Actualizar la hoja de trabajo en el parent
        if hasattr(self.parent, 'cargar_datos'):
            self.parent.cargar_datos()

    # ==================== GUARDADO (FLUJO NUEVO / EDITAR) ====================
    
    def _on_confirmar(self, e):
        """Handler unificado del botón principal (nuevo/editar)."""
        self.guardar(e)
    
    def guardar(self, e):
        """
        Punto de entrada de guardado desde la UI.
        Valida el formulario antes de guardar.
        Redirige a:
        - `_guardar_nuevo()`  si modo = 'nuevo'
        - `_guardar_edicion()` si modo = 'editar'
        """
        if not self._validacion_formulario_exitosa():
            return
        self._guardar_segun_modo()

    def _validacion_formulario_exitosa(self) -> bool:
        """Centraliza validación + feedback visual antes de ejecutar guardado."""
        if self._validar_formulario():
            return True
        self._mostrar_error_validacion_guardado()
        self.page.update()
        return False

    def _mostrar_error_validacion_guardado(self) -> None:
        """
        Mensaje estándar de error de validación.
        En `nuevo` sin tercero, `_validar_formulario` ya deja un mensaje específico.
        """
        if self.modo == "nuevo" and not self.tercero_actual:
            return
        actualizar_mensaje_en_control(
            "Revise los campos marcados con error antes de guardar.", self.mensaje
        )

    def _guardar_segun_modo(self) -> None:
        """Despacha el guardado según el modo activo del diálogo."""
        if self.modo == "fideicomiso_masivo":
            self._guardar_fideicomiso_masivo()
            return
        accion = self._accion_guardado_payload_por_modo()
        self._guardar_con_payload(accion)

    def _accion_guardado_payload_por_modo(self):
        """Retorna la acción de persistencia correspondiente al modo nuevo/editar."""
        if self.modo == "editar":
            return lambda payload: self._mutar_hoja().actualizar_entrada_hoja_trabajo(
                self.id_concepto, self.identidad, payload
            )
        return lambda payload: self._mutar_hoja().crear_entrada_hoja_trabajo(payload)
    
    def _validar_formulario(self):
        """
        Valida todos los campos del formulario usando error_text.
        Retorna True si todos los campos son válidos, False en caso contrario.
        """
        self._limpiar_errores_campos()

        if self.modo == "fideicomiso_masivo":
            return self._validar_formulario_fideicomiso()

        if not self._validar_tercero_requerido_nuevo():
            return False

        errores = self._validar_campos_formulario_principal()
        return not errores

    def _limpiar_errores_campos(self) -> None:
        """Limpia estado visual de error en todos los controles editables."""
        for campo in self.campos.values():
            set_campo_error(campo, None)

    def _validar_formulario_fideicomiso(self) -> bool:
        """Valida selección de tipo/subtipo cuando el diálogo está en modo masivo."""
        tipo_ok = False
        subtipo_ok = False
        for attr, ctrl in self.campos.items():
            key = str(attr or "").strip().upper()
            valor = str(getattr(ctrl, "value", "") or "").strip()
            if key == "TIPO DE FIDEICOMISO":
                tipo_ok = bool(valor)
                if not tipo_ok:
                    set_campo_error(ctrl, "Seleccione el tipo de fideicomiso.")
            elif key == "SUBTIPO DE FIDEICOMISO":
                subtipo_ok = bool(valor)
                if not subtipo_ok:
                    set_campo_error(ctrl, "Seleccione el subtipo de fideicomiso.")
        self.page.update()
        return tipo_ok and subtipo_ok

    def _validar_tercero_requerido_nuevo(self) -> bool:
        """En modo nuevo exige tercero seleccionado antes de persistir."""
        if self.modo != "nuevo" or self.tercero_actual:
            return True
        actualizar_mensaje_en_control(
            "Seleccione un tercero antes de guardar.",
            self.mensaje,
        )
        return False

    def _valor_control_normalizado(self, ctrl, attr: str) -> str:
        """Lee `value` de un control y normaliza formato monetario cuando aplica."""
        valor = ctrl.value if hasattr(ctrl, "value") else None
        valor_str = str(valor).strip() if valor else ""
        if valor_str and self._es_atributo_valor(attr):
            return self._normalizar_valor_monetario(valor_str)
        return valor_str

    def _validar_campos_formulario_principal(self) -> bool:
        """Valida campos del formulario estándar (nuevo/editar). Retorna `True` si hay errores."""
        errores = False

        for attr, ctrl in self.campos.items():
            tipoacumulado = self.atributos_info.get(attr, 0)
            # Los de tercero no están en el grid; vienen de la tarjeta / selección.
            if self._es_campo_de_tercero(tipoacumulado, attr):
                continue

            valor_str = self._valor_control_normalizado(ctrl, attr)

            if self._es_atributo_identificacion(attr):
                if not aplicar_validacion_error_text(
                    ctrl,
                    valor_str,
                    validar_campo_obligatorio,
                    nombre_campo="Número de Identificación",
                ):
                    errores = True
                    continue

            if valor_str and self._es_atributo_numerico(attr):
                if not aplicar_validacion_error_text(
                    ctrl, valor_str, validar_numero, tipo="float", min_val=0
                ):
                    errores = True
                    continue
            if valor_str and self._es_atributo_correo(attr):
                if not aplicar_validacion_error_text(ctrl, valor_str, validar_email):
                    errores = True

        return errores


    def _post_guardar(self, resultado):
        """Manejo común posterior al intento de guardado."""
        if resultado is False:
            actualizar_mensaje_en_control(resultado, self.mensaje)
        else:
            actualizar_mensaje_en_control("Guardado correctamente", self.mensaje, ft.Colors.GREEN_300)
            self.parent.cargar_datos()
        self.page.update()

    def _guardar_nuevo(self):
        """Guarda un nuevo grupo de filas de hoja de trabajo (modo 'nuevo')."""
        self._guardar_con_payload(
            lambda payload: self._mutar_hoja().crear_entrada_hoja_trabajo(payload)
        )

    def _guardar_edicion(self):
        """Actualiza un registro existente de hoja de trabajo (modo 'editar')."""
        self._guardar_con_payload(
            lambda payload: self._mutar_hoja().actualizar_entrada_hoja_trabajo(
                self.id_concepto, self.identidad, payload
            )
        )

    def _guardar_con_payload(self, accion_guardado):
        """Construye payload y ejecuta una acción de persistencia reutilizable."""
        datos_para_guardar = self._construir_payload_guardado()
        resultado = accion_guardado(datos_para_guardar)
        self._post_guardar(resultado)

    def _fideicomiso_ui_ocupado(self, ocupado: bool) -> None:
        """Ring + deshabilitar confirmar mientras corre el guardado masivo."""
        if ocupado:
            loader_row_trabajo(self.page, self.loader_fideicomiso, self.mensaje, "Aplicando cambios masivos...")
        else:
            loader_row_fin(self.page, self.loader_fideicomiso)
            self.mensaje.visible = True
        if self._btn_confirmar_dialogo:
            self._btn_confirmar_dialogo.disabled = ocupado

    def _valores_formulario_fideicomiso(self) -> tuple[str, str, str, str]:
        """tipo, subtipo nuevos y filtros por valor actual (strings)."""
        datos_formulario = self._recopilar_datos_formulario()
        tipo = self._valor_por_descripcion(datos_formulario, "TIPO DE FIDEICOMISO")
        subtipo = self._valor_por_descripcion(datos_formulario, "SUBTIPO DE FIDEICOMISO")
        ft = str(self.filtro_tipo_actual.value or "").strip() if self.filtro_tipo_actual else ""
        fs = str(self.filtro_subtipo_actual.value or "").strip() if self.filtro_subtipo_actual else ""
        return tipo, subtipo, ft, fs

    def _valor_por_descripcion(self, datos: dict, descripcion_mayuscula: str) -> str:
        """Busca valor por descripción normalizada del atributo en un payload de formulario."""
        for k, v in datos.items():
            if str(k or "").strip().upper() == descripcion_mayuscula:
                return str(v or "").strip()
        return ""

    def _guardar_fideicomiso_masivo(self):
        """Aplica tipo/subtipo de fideicomiso (en hilo; usa loader reutilizable)."""
        tipo, subtipo, filtro_tipo, filtro_subtipo = self._valores_formulario_fideicomiso()
        self._fideicomiso_ui_ocupado(True)
        self.page.update()

        def _worker():
            resultado = self._ejecutar_fideicomiso_masivo(
                tipo=tipo,
                subtipo=subtipo,
                filtro_tipo=filtro_tipo,
                filtro_subtipo=filtro_subtipo,
            )
            self._procesar_resultado_fideicomiso_masivo(resultado)

        self.page.run_thread(_worker)

    def _ejecutar_fideicomiso_masivo(
        self, *, tipo: str, subtipo: str, filtro_tipo: str, filtro_subtipo: str
    ):
        """Invoca el caso de uso de actualización masiva con los filtros seleccionados."""
        return self._mutar_hoja().actualizar_fideicomiso_masivo(
            self.concepto,
            tipo,
            subtipo,
            filtro_tipo_actual=filtro_tipo,
            filtro_subtipo_actual=filtro_subtipo,
        )

    def _fideicomiso_masivo_exitoso(self, resultado) -> bool:
        """Determina éxito con la misma regla histórica basada en el texto de retorno."""
        return isinstance(resultado, str) and resultado.lower().startswith("tipo y subtipo")

    def _procesar_resultado_fideicomiso_masivo(self, resultado) -> None:
        """Aplica feedback de UI, recarga y cierre de estado para el guardado masivo."""
        self._fideicomiso_ui_ocupado(False)
        if self._fideicomiso_masivo_exitoso(resultado):
            actualizar_mensaje_en_control(resultado, self.mensaje, ft.Colors.GREEN_300)
            self.parent.cargar_datos()
        else:
            actualizar_mensaje_en_control(
                resultado if isinstance(resultado, str) else "Error aplicando fideicomiso masivo.",
                self.mensaje,
            )
        self.page.update()

    # ==================== UTILIDADES ====================
    
    def _label(self, key, name):
        """Crea etiqueta con formato 'key | name'."""
        if isinstance(name, list):
            name = name[1]
        return f"{key} | {name}"
    
    def _key_from_label(self, label):
        """Extrae la clave del formato 'key | name'."""
        if label is None:
            return ""
        if isinstance(label, (int, float)):
            return str(label)
        s = str(label)
        if " | " in s:
            return s.split(" | ", 1)[0].strip()
        return s
    
    def _es_campo_de_tercero(self, tipoacumulado, attr: str | None = None):
        """Determina si un campo va en tarjeta de contexto (T/C/B/A); excluye CLASE=2."""
        if attr and self._es_clase_atributo(attr, 2):
            return False
        tipo_global, codigo = self._parse_tipoacumulado_contexto(tipoacumulado)
        if codigo is None:
            return False
        # Mantiene regla histórica por rango y habilita prefijos globales C/B/A además de T.
        if tipo_global and tipo_global not in {"T", "C", "B", "A"}:
            return False
        return 1000 <= codigo < 9000

    def _parse_tipoacumulado_contexto(self, tipoacumulado) -> tuple[str | None, int | None]:
        """Normaliza `tipoacumulado` en forma (global, codigo) aceptando T/C/B/A y formato legacy."""
        raw = str(tipoacumulado or "").strip().upper()
        if not raw:
            return None, None

        if raw[:1] in {"T", "C", "B", "A"}:
            digitos = "".join(ch for ch in raw[1:] if ch.isdigit())
            if not digitos:
                return raw[:1], None
            try:
                return raw[:1], int(digitos)
            except ValueError:
                return raw[:1], None

        try:
            return None, int(raw)
        except ValueError:
            return None, None

    def _es_atributo_identificacion(self, attr: str) -> bool:
        """Detecta atributos que representan número de identificación."""
        attr_upper = str(attr or "").upper()
        return (
            attr == "Número de Identificación"
            or "IDENTIFICACION" in attr_upper
            or "IDENTIFICACIÓN" in attr_upper
        )

    def _es_clase_atributo(self, attr: str, clase_esperada: int) -> bool:
        """Compara ATRIBUTOS.CLASE (cargada en `atributos_clase`) con un valor entero."""
        raw = self.atributos_clase.get(attr, "")
        try:
            return int(raw) == clase_esperada
        except (TypeError, ValueError):
            return str(raw).strip() == str(clase_esperada)

    def _es_atributo_correo(self, attr: str) -> bool:
        """CLASE=3 y descripción sugiere correo electrónico (validación con `validar_email`)."""
        if not self._es_clase_atributo(attr, 3):
            return False
        au = str(attr or "").upper()
        return "EMAIL" in au or "CORREO" in au

    def _es_atributo_numerico(self, attr: str) -> bool:
        """
        Atributos numéricos en UI/validación: CLASE=1 (valor/monto), heurística por texto,
        y CLASE=3 con identificación/identidad/porcentaje en la descripción (no correo).
        """
        if self._es_atributo_correo(attr):
            return False
        try:
            if int(self.atributos_clase.get(attr, 0) or 0) == 1:
                return True
        except (TypeError, ValueError):
            pass
        attr_upper = str(attr or "").upper()
        if any(
            palabra in attr_upper
            for palabra in ("MONTO", "VALOR", "CANTIDAD", "PORCENTAJE", "BASE", "GRAVABLE", "IMPUESTO")
        ):
            return True
        if self._es_clase_atributo(attr, 3) and any(
            palabra in attr_upper for palabra in ("IDENTIFICACION", "IDENTIFICACIÓN", "IDENTIDAD")
        ):
            return True
        return False

    def _es_atributo_valor(self, attr: str) -> bool:
        """True cuando el atributo es CLASE=1 (valor monetario)."""
        return self._es_clase_atributo(attr, 1)

    def _normalizar_valor_monetario(self, valor: object) -> str:
        """
        Convierte texto monetario de UI a número canónico (punto decimal, sin miles).
        Ejemplos: "1.234.567,89" -> "1234567.89", "1,5" -> "1.5", "1200" -> "1200".
        """
        if valor is None:
            return ""
        s = str(valor).strip()
        if not s:
            return ""
        s = s.replace(" ", "")
        if "," in s and "." in s:
            return s.replace(".", "").replace(",", ".")
        if "," in s:
            return s.replace(",", ".")
        if s.count(".") > 1:
            return s.replace(".", "")
        return s

    def _concepto_tiene_codigo_y_formato(self) -> bool:
        """Indica si self.concepto viene como dict con codigo y formato."""
        return isinstance(self.concepto, dict) and "codigo" in self.concepto and "formato" in self.concepto

    def _obtener_atributos_concepto(self):
        """
        Retorna atributos del concepto activo con compatibilidad para payload dict (codigo/formato)
        y formato legacy.
        """
        if self._concepto_tiene_codigo_y_formato():
            concepto_ref = {
                "codigo": str(self.concepto["codigo"]),
                "formato": str(self.concepto["formato"]),
            }
            return self._formatos_uc.obtener_atributos_por_concepto(concepto_ref)
        return self._formatos_uc.obtener_atributos_por_concepto(self.concepto)

    def _asignar_concepto_y_formato(self, datos_destino: dict):
        """
        Asigna Concepto/FORMATO en el payload de trabajo.
        Mantiene compatibilidad con flujos donde concepto no viene como dict.
        """
        if self._concepto_tiene_codigo_y_formato():
            datos_destino["Concepto"] = self.concepto["codigo"]
            datos_destino["FORMATO"] = self.concepto["formato"]
        else:
            datos_destino["Concepto"] = self.concepto

    def _construir_payload_guardado(self) -> dict:
        """Arma payload final de guardado con datos de formulario y metadatos de concepto/formato."""
        payload = self._recopilar_datos_formulario()
        self._asignar_concepto_y_formato(payload)
        return payload

    def _control_usa_key_from_label(self, ctrl) -> bool:
        """True si el control requiere extraer código desde etiqueta 'key | name'."""
        if isinstance(ctrl, DropdownCompact):
            return True
        raw_label = getattr(ctrl, "label", "") or ""
        # Algunos controles exponen `label` como ft.Text en lugar de string.
        label = str(getattr(raw_label, "value", raw_label) or "").strip()
        lower_label = label.lower()
        return (
            ctrl in (self.drop_dep, self.drop_mun)
            or "país" in lower_label
            or "pais" in lower_label
            or ("tipo" in lower_label and "documento" in lower_label)
        )

    # ==================== CARGA DE DATOS ====================
    
    def _cargar_tercero_actual(self):
        """
        Carga el tercero asociado al registro actual.
        Solo se usa en modo 'editar' antes de construir el formulario.
        """
        identidad = self.datos.get("Número de Identificación")
        if identidad:
            terceros_lista, _total = self._terceros_uc.obtener_terceros(offset=0, limit=1, filtro=[identidad])
            self.tercero_actual = terceros_lista[0].copy() if terceros_lista else None
        else:
            self.tercero_actual = None
    
    def _atributos_descripciones_orden_por_id(self) -> list[str]:
        """
        Descripciones de atributos con tipoacumulado < 9000, ordenadas por ID de atributo
        (misma regla que hoja_tools_front.construir_esquema / columnas de la grilla).
        """
        lista = self._obtener_atributos_concepto()
        attrs = sorted(
            lista,
            key=lambda a: int(a[0]) if (isinstance(a[0], (int, float)) or str(a[0]).isdigit()) else 0,
        )
        out: list[str] = []
        for a in attrs:
            if len(a) < 5 or (a[4] or 0) >= 9000:
                continue
            d = (a[2] or "").strip()
            if d:
                out.append(d)
        return out

    def _orden_campos_formulario(self) -> list[str]:
        """Orden de filas del formulario: ID atributo; al final, claves en datos no listadas en el concepto."""
        excluir = {"Concepto", "FORMATO", "id_concepto"}
        keys_datos = {k for k in self.datos if k not in excluir}
        schema = self._atributos_descripciones_orden_por_id()
        orden = [d for d in schema if d in keys_datos]
        extras = sorted(k for k in keys_datos if k not in orden)
        return orden + extras

    def _cargar_atributos_info(self):
        """Carga y organiza la información de atributos del concepto."""
        lista_campos = self._obtener_atributos_concepto()
        # Tupla: (ID, NOMBRE, DESCRIPCION, CLASE, TIPOACUMULADO); tipoacumulado < 9000; orden por ID como la grilla
        lista_campos_sincab = sorted(
            [campo for campo in lista_campos if len(campo) >= 5 and (campo[4] or 0) < 9000],
            key=lambda a: int(a[0]) if (isinstance(a[0], (int, float)) or str(a[0]).isdigit()) else 0,
        )
        # Construir diccionario, priorizando tipoacumulado >= 1000 en duplicados
        self.atributos_info = {}
        self.atributos_clase = {}
        self.atributos_nombre = {}
        self.atributos_id = {}
        self._cache_padre_catalogo = {}
        for campo in lista_campos_sincab:
            # Usamos la DESCRIPCION (campo[2]) como etiqueta visible
            # y TIPOACUMULADO (campo[4]) para la lógica de terceros / editables.
            attr_id = campo[0]
            nombre_atributo = campo[1]
            descripcion = campo[2]
            tipoacumulado = campo[4] or 0
            clase = campo[3] or 0

            self.atributos_clase[descripcion] = clase
            self.atributos_nombre[descripcion] = nombre_atributo
            self.atributos_id[descripcion] = attr_id
            
            if descripcion in self.atributos_info:
                tipo_anterior = self.atributos_info[descripcion]
                if tipoacumulado >= 1000 and tipo_anterior < 1000:
                    self.atributos_info[descripcion] = tipoacumulado
            else:
                self.atributos_info[descripcion] = tipoacumulado

    def _imprimir_atributos_en_consola(self) -> None:
        """
        Registra en consola el esquema de atributos y el valor en `self.datos` por descripción
        (mismo orden que la grilla: ID ascendente, sin cabeceras tipoacumulado >= 9000).
        Debe llamarse después de `_asegurar_datos_completos` para que los valores reflejen el formulario.
        """
        orden = self._atributos_descripciones_orden_por_id()
        print(
            "[TrabajoDialog] construcción formulario | modo=%s id_concepto=%s identidad=%s concepto=%r"
            % (self.modo, self.id_concepto, self.identidad, self.concepto)
        )
        for desc in orden:
            raw = self.datos.get(desc, "")
            val_str = "" if raw is None else str(raw)
            if len(val_str) > 160:
                val_str = val_str[:157] + "..."
            print(
                "  atributo id=%r nombre=%r descripcion=%r clase=%r tipoacumulado=%r valor=%r"
                % (
                    self.atributos_id.get(desc),
                    self.atributos_nombre.get(desc),
                    desc,
                    self.atributos_clase.get(desc),
                    self.atributos_info.get(desc),
                    val_str,
                )
            )
        print("[TrabajoDialog] total atributos (formulario): %s" % len(orden))

    # ==================== CONSTRUCCIÓN DE CONTROLES UI ====================
    
    def _crear_dropdown_base(self, label, options_iterable, key_value=None, on_change=None, disabled=False):
        """Crea un dropdown con opciones formateadas."""
        opts = []
        selected_value = None
        
        for opt in options_iterable:
            if isinstance(opt, (list, tuple)) and len(opt) >= 2:
                k, v = str(opt[0]), opt[1]
                label_text = self._label(k, v)
            else:
                k = str(opt)
                label_text = k
            
            opts.append(ft.DropdownOption(key=label_text, text=label_text))
            if key_value is not None and k == str(key_value):
                selected_value = label_text
        
        lbl_vis = str(label or "").strip()
        return DropdownCompact(
            label=lbl_vis,
            options=opts,
            value=selected_value or None,
            on_select=on_change,
            width=self._ancho_control(label),
            expand=False,
            disabled=disabled,
            tooltip=label,
        )
    
    def _crear_textfield(
        self,
        label,
        value,
        multiline=False,
        disabled=False,
        width: int | None = None,
        keyboard_type: ft.KeyboardType | None = None,
        max_length: int | None = None,
    ):
        """Crea un TextField Material; `label` como `ft.Text` para forzar máx 2 líneas con elipsis."""
        # lbl_full = _label_sin_conjuncion_huerfana(label)
        etiqueta = ft.Text(
            label,
            color=GREY_700,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        kw: dict = dict(
            label=etiqueta,
            value=value,
            border_color=PINK_200,
            multiline=multiline,
            max_lines=4 if multiline else 1,
            read_only=disabled,
            bgcolor=ft.Colors.GREY_100 if disabled else None,
            width=width,
            content_padding=ft.padding.only(left=12, right=12, top=12, bottom=12),
            tooltip=label,
        )
        if keyboard_type is not None:
            kw["keyboard_type"] = keyboard_type
        if max_length is not None:
            kw["max_length"] = max_length
        return ft.TextField(**kw)
    
    def _es_attr_razon_social(self, attr: str) -> bool:
        """Razón social ocupa el ancho de dos campos normales (fila completa en el grid de 12)."""
        al = (attr or "").lower()
        return ("razón" in al or "razon" in al) and "social" in al

    def _ancho_control(self, attr: str) -> int:
        """
        Resuelve el ancho del control editable por atributo.
        Orden de prioridad: razón social > exacto > contiene > default.
        """
        etiqueta = str(attr or "").strip()
        al = etiqueta.lower()
        if self._es_attr_razon_social(attr):
            return self.ANCHO_RAZON_SOCIAL
        for k, w in self.ANCHO_POR_ATRIBUTO_EXACTO.items():
            if str(k or "").strip().lower() == al:
                return int(w)
        for patron, w in self.ANCHO_POR_ATRIBUTO_CONTIENE.items():
            if all(str(p).lower() in al for p in patron):
                return int(w)
        return self.ANCHO_CONTROL_DEFAULT

    def _dropdown_vacio_datos_especificos(
        self,
        attr: str,
        es_editable: bool,
        on_select,
    ) -> DropdownCompact:
        """Dropdown sin opciones iniciales (país/disparadores llenan después)."""
        return DropdownCompact(
            label=str(attr or "").strip(),
            options=[],
            value=None,
            on_select=on_select,
            width=self._ancho_control(attr),
            expand=False,
            disabled=not es_editable,
            tooltip=attr,
        )

    def _crear_control_texto_predeterminado(self, attr, val, es_editable):
        """TextField/multiline por defecto: valores monetarios formateados y teclado numérico cuando aplica."""
        val_texto = str(val or "")
        multiline = len(val_texto) > 80 or self._es_attr_razon_social(attr)
        valor_inicial = (
            formatear_pesos(val_texto)
            if self._es_atributo_valor(attr) and val_texto
            else val
        )
        kbd = (
            ft.KeyboardType.NUMBER
            if (self._es_atributo_numerico(attr) and not multiline)
            else None
        )
        return self._crear_textfield(
            attr,
            valor_inicial,
            multiline,
            disabled=not es_editable,
            width=self._ancho_control(attr),
            keyboard_type=kbd,
        )

    def _crear_control(self, attr, val, tipoacumulado, es_editable):
        """Crea el control UI según el tipo de atributo."""
        upper_attr = attr.upper()

        if self._es_clase_atributo(attr, 2):
            return self._dropdown_datos_especificos(attr)
        if "PAÍS" in upper_attr or "PAÃ" in upper_attr or "PAIS" in upper_attr:
            return self._crear_dropdown_base(
                attr,
                PAISES.items(),
                str(val) if val else None,
                on_change=self._on_pais_change,
                disabled=not es_editable,
            )

        es_tipo_doc_por_nombre = (
            ("DOCUMENTO" in upper_attr and "TIPO" in upper_attr)
            or attr.strip().lower().startswith("tipo de documento")
        )
        if es_tipo_doc_por_nombre and self._es_clase_atributo(attr, 3):
            return self._crear_dropdown_base(
                attr, TIPOSDOC.items(), str(val) if val else None, disabled=not es_editable
            )

        if "DEPARTAMENTO" in upper_attr:
            self.drop_dep = self._dropdown_vacio_datos_especificos(
                attr, es_editable, self._on_departamento_change
            )
            return self.drop_dep

        if "MUNICIPIO" in upper_attr:
            self.drop_mun = self._dropdown_vacio_datos_especificos(attr, es_editable, None)
            return self.drop_mun

        return self._crear_control_texto_predeterminado(attr, val, es_editable)

    # ==================== MAPEO Y VALIDACIÓN ====================
    
    def _mapear_tercero_a_atributo(self, campo_tercero, descripcion_atributo):
        """Verifica si un campo de tercero mapea a un atributo."""
        desc = str(descripcion_atributo).upper()
        campo = campo_tercero.lower()
        grupos = self.MAPEO_TERCERO_ATRIBUTO.get(campo)
        
        if not grupos:
            return False
        
        return all(any(palabra in desc for palabra in grupo) for grupo in grupos)
    
    def _obtener_descripcion_atributo(self, campo_buscar):
        """Obtiene la descripción del atributo que mapea a un campo del tercero."""
        for descripcion, tipoacumulado in self.atributos_info.items():
            if self._es_campo_de_tercero(tipoacumulado, descripcion):
                if self._mapear_tercero_a_atributo(campo_buscar, descripcion):
                    return descripcion
        return None

    # ==================== APLICACIÓN DE DATOS ====================
    
    def _aplicar_tercero_seleccionado(self, tercero):
        """Aplica los datos del tercero seleccionado a self.datos y refresca el contenido del diálogo."""
        self.tercero_actual = tercero
        
        for descripcion, tipoacumulado in self.atributos_info.items():
            if self._es_campo_de_tercero(tipoacumulado, descripcion):
                for campo_tercero, valor_tercero in tercero.items():
                    if self._mapear_tercero_a_atributo(campo_tercero, descripcion):
                        if campo_tercero == "tipodocumento":
                            codigo_tipo = obtener_codigo_tipodoc(valor_tercero)
                            self.datos[descripcion] = codigo_tipo if codigo_tipo else str(valor_tercero) if valor_tercero else ""
                        else:
                            self.datos[descripcion] = str(valor_tercero) if valor_tercero else ""
                        break
        
        if self.dialog:
            # Conservar lo ya escrito en el grid antes de reconstruir controles.
            self.datos.update(self._valores_desde_controles_solo_grid())
            self._refrescar_contenido_dialogo()
        else:
            self._build_dialogo_formulario()

    def _refrescar_contenido_dialogo(self):
        """Reconstruye solo el content del diálogo (sin recrear acciones/título)."""
        if not self.dialog:
            return
        controles = self._construir_grid_campos()
        self.dialog.content = self._construir_contenido_dialogo(controles)
        self._inicializar_dropdowns_dependientes()
        self.page.update()

    # ==================== CONSTRUCCIÓN DE DIÁLOGOS ====================
    
    def _build_dialogo_formulario(self):
        """
        Construye el diálogo principal de formulario.
        Se usa tanto en modo 'nuevo' como en modo 'editar'.
        """
        self._preparar_estado_dialogo_formulario()
        controles = self._construir_grid_campos()
        contenido = self._construir_contenido_dialogo(controles)
        self.dialog = self._crear_dialogo(contenido)
        self._mostrar_dialogo_formulario()

    def _preparar_estado_dialogo_formulario(self) -> None:
        """Carga estado previo y metadatos necesarios antes de renderizar controles."""
        if self.modo == "editar":
            self.formato = self.datos.get("FORMATO", "")
        self._cargar_atributos_info()
        self._asegurar_datos_completos()
        self._imprimir_atributos_en_consola()

    def _mostrar_dialogo_formulario(self) -> None:
        """Inicializa dependencias del diálogo y lo muestra en pantalla."""
        self._inicializar_dropdowns_dependientes()
        self.page.show_dialog(self.dialog)
        self.page.update()
    
    def _asegurar_datos_completos(self):
        """Garantiza que self.datos tenga todas las columnas del concepto."""
        attrs = [
            c[2]
            for c in self._obtener_atributos_concepto()
            if len(c) >= 5 and (c[4] or 0) < 9000
        ]
        if self.modo == "nuevo" and not self.tercero_actual:
            self.datos = {d: "" for d in attrs}
            self._asignar_concepto_y_formato(self.datos)
            self.datos["Número de Identificación"] = ""
        else:
            for d in attrs:
                if d not in self.datos:
                    self.datos[d] = ""

    def _construir_grid_campos(self):
        """Construye controles editables en orden (una lista lineal de controles)."""
        excluir = {"Concepto", "FORMATO", "id_concepto"}
        datos = {k: v for k, v in self.datos.items() if k not in excluir}

        self.campos = {}
        controles: list[tuple[str, ft.Control]] = []
        for attr in self._orden_campos_formulario():
            if self.modo == "fideicomiso_masivo":
                attr_u = str(attr or "").strip().upper()
                if attr_u not in {"TIPO DE FIDEICOMISO", "SUBTIPO DE FIDEICOMISO"}:
                    continue
            val = datos.get(attr, "")
            tipo = self.atributos_info.get(attr, 0)
            # Grid: solo CLASE 1/2/3 (CLASE 2 = datos específicos). Tercero va en tarjeta.
            if not any(self._es_clase_atributo(attr, c) for c in (1, 2, 3)):
                continue
            ctrl = self._crear_control(attr, val, tipo, True)
            self.campos[attr] = ctrl
            controles.append((attr, ctrl))
        self._enlazar_tipos_con_subtipos()
        return controles
    
    def _construir_filas_grid_formulario(self, controles: list[tuple[str, ft.Control]]) -> list[ft.Row]:
        """
        Filas bajo la tarjeta de tercero.
        2 cols (fideicomiso masivo): orden del concepto.
        3 cols (nuevo/editar): datos específicos (CLASE=2), manuales (CLASE=3), valores (CLASE=1).
        """
        margen_horizontal = 6
        padding_celda = 9
        ancho_normal = self._ancho_normal_grid(controles)

        if self.modo in ("nuevo", "editar"):
            return self._filas_grid_tres_columnas(
                controles=controles,
                margen_horizontal=margen_horizontal,
                padding_celda=padding_celda,
                ancho_normal=ancho_normal,
            )
        return self._filas_grid_dos_columnas(
            controles=controles,
            margen_horizontal=margen_horizontal,
            padding_celda=padding_celda,
            ancho_normal=ancho_normal,
        )

    def _ancho_normal_grid(self, controles: list[tuple[str, ft.Control]]) -> int:
        """Ancho base para celdas vacías y cálculo de filas completas."""
        ancho_normal = 233
        for attr, _ in controles:
            if not self._es_attr_razon_social(attr):
                return self._ancho_control(attr)
        return ancho_normal

    def _wrap_cell_grid(self, attr: str, ctrl: ft.Control, padding_celda: int) -> ft.Container:
        return ft.Container(
            width=self._ancho_control(attr),
            padding=padding_celda,
            expand=False,
            content=ctrl,
        )

    def _empty_cell_grid(self, ancho_normal: int, padding_celda: int) -> ft.Container:
        return ft.Container(
            width=ancho_normal,
            padding=padding_celda,
            expand=False,
        )

    def _fila_grid_dos_celdas(
        self,
        celda_izq: ft.Container,
        celda_der: ft.Container,
        margen_horizontal: int,
    ) -> ft.Row:
        """Una fila del grid de dos columnas con el mismo spacing histórico."""
        return ft.Row([celda_izq, celda_der], spacing=margen_horizontal)

    def _fila_razon_social_grid(
        self, ancho_fila: int, ctrl: ft.Control, padding_celda: int
    ) -> ft.Row:
        return ft.Row(
            [
                ft.Container(
                    width=ancho_fila,
                    padding=padding_celda,
                    expand=False,
                    content=ctrl,
                )
            ],
            spacing=0,
        )

    def _filas_grid_dos_columnas(
        self,
        *,
        controles: list[tuple[str, ft.Control]],
        margen_horizontal: int,
        padding_celda: int,
        ancho_normal: int,
    ) -> list[ft.Row]:
        """Emparejado secuencial de dos columnas (mismo comportamiento histórico)."""
        filas: list[ft.Row] = []
        pendiente: tuple[str, ft.Control] | None = None
        for attr, ctrl in controles:
            if self._es_attr_razon_social(attr):
                if pendiente is not None:
                    a1, c1 = pendiente
                    filas.append(
                        self._fila_grid_dos_celdas(
                            self._wrap_cell_grid(a1, c1, padding_celda),
                            self._empty_cell_grid(ancho_normal, padding_celda),
                            margen_horizontal,
                        )
                    )
                    pendiente = None
                filas.append(
                    self._fila_razon_social_grid(
                        self._ancho_control(attr), ctrl, padding_celda
                    )
                )
                continue
            if pendiente is None:
                pendiente = (attr, ctrl)
            else:
                a1, c1 = pendiente
                filas.append(
                    self._fila_grid_dos_celdas(
                        self._wrap_cell_grid(a1, c1, padding_celda),
                        self._wrap_cell_grid(attr, ctrl, padding_celda),
                        margen_horizontal,
                    )
                )
                pendiente = None
        if pendiente is not None:
            a1, c1 = pendiente
            filas.append(
                self._fila_grid_dos_celdas(
                    self._wrap_cell_grid(a1, c1, padding_celda),
                    self._empty_cell_grid(ancho_normal, padding_celda),
                    margen_horizontal,
                )
            )
        return filas

    def _fila_titulo_bloque_grid(self, texto: str, ancho_fila_completa: int, padding_celda: int) -> ft.Row:
        return ft.Row(
            [
                ft.Container(
                    width=ancho_fila_completa,
                    padding=ft.padding.only(left=padding_celda, right=padding_celda, top=8, bottom=4),
                    content=ft.Column(
                        [
                            ft.Text(texto, size=12, weight=ft.FontWeight.W_600, color=GREY_700, margin=ft.margin.only(top=-12)),
                            ft.Divider(height=0, thickness=1, color=ft.Colors.GREY_300),
                        ],
                        spacing=0,
                    ),
                )
            ],
            spacing=0,
        )

    def _flush_buffer_grid_tres_columnas(
        self,
        buffer_controles: list[tuple[str, ft.Control]],
        *,
        filas3: list[ft.Row],
        margen_horizontal: int,
        padding_celda: int,
        ancho_fila_completa: int,
        ancho_normal: int,
    ) -> None:
        """Vuelca el buffer al grid solo si tiene ítems (evita llamadas repetidas con los mismos kwargs)."""
        if not buffer_controles:
            return
        self._volcar_buffer_tres_columnas(
            filas3=filas3,
            buffer_controles=buffer_controles,
            margen_horizontal=margen_horizontal,
            padding_celda=padding_celda,
            ancho_fila_completa=ancho_fila_completa,
            ancho_normal=ancho_normal,
        )

    def _volcar_buffer_tres_columnas(
        self,
        *,
        filas3: list[ft.Row],
        buffer_controles: list[tuple[str, ft.Control]],
        margen_horizontal: int,
        padding_celda: int,
        ancho_fila_completa: int,
        ancho_normal: int,
    ) -> None:
        for j in range(0, len(buffer_controles), 3):
            chunk = buffer_controles[j : j + 3]
            if len(chunk) < 3 and all(isinstance(c, DropdownCompact) for _, c in chunk):
                cells_expand: list[ft.Container] = []
                for _, ctrl in chunk:
                    if ctrl.controls and isinstance(ctrl.controls[0], ft.Container):
                        ctrl.controls[0].width = None
                        ctrl.controls[0].expand = 1
                    ctrl.expand = 1
                    cells_expand.append(
                        ft.Container(padding=padding_celda, expand=1, content=ctrl)
                    )
                filas3.append(
                    ft.Row(
                        cells_expand,
                        spacing=margen_horizontal,
                        width=ancho_fila_completa,
                    )
                )
                continue
            celdas = [self._wrap_cell_grid(a, c, padding_celda) for a, c in chunk]
            while len(celdas) < 3:
                celdas.append(self._empty_cell_grid(ancho_normal, padding_celda))
            filas3.append(ft.Row(celdas[:3], spacing=margen_horizontal))

    def _filas_grid_tres_columnas(
        self,
        *,
        controles: list[tuple[str, ft.Control]],
        margen_horizontal: int,
        padding_celda: int,
        ancho_normal: int,
    ) -> list[ft.Row]:
        """Construye grid por secciones para nuevo/editar (3 columnas)."""
        especificos = [(a, c) for a, c in controles if self._es_clase_atributo(a, 2)]
        manuales = [(a, c) for a, c in controles if self._es_clase_atributo(a, 3)]
        valores = [(a, c) for a, c in controles if self._es_clase_atributo(a, 1)]
        ancho_fila_completa = 3 * (ancho_normal + 2 * padding_celda) + 2 * margen_horizontal
        filas3: list[ft.Row] = []

        secciones = [
            ("Datos especificos (DIAN)", especificos),
            ("Atributos manuales", manuales),
            ("Atributos de valores", valores),
        ]
        for titulo, grupo in secciones:
            if not grupo:
                continue
            if filas3:
                filas3.append(ft.Row([ft.Container(height=1)], spacing=0))
            filas3.append(
                self._fila_titulo_bloque_grid(titulo, ancho_fila_completa, padding_celda)
            )

            buffer_controles: list[tuple[str, ft.Control]] = []
            def flush_buf() -> None:
                self._flush_buffer_grid_tres_columnas(
                    buffer_controles,
                    filas3=filas3,
                    margen_horizontal=margen_horizontal,
                    padding_celda=padding_celda,
                    ancho_fila_completa=ancho_fila_completa,
                    ancho_normal=ancho_normal,
                )

            for attr, ctrl in grupo:
                if self._es_attr_razon_social(attr):
                    if buffer_controles:
                        flush_buf()
                        buffer_controles.clear()
                    filas3.append(
                        self._fila_razon_social_grid(
                            ancho_fila_completa, ctrl, padding_celda
                        )
                    )
                else:
                    buffer_controles.append((attr, ctrl))
                    if len(buffer_controles) == 3:
                        flush_buf()
                        buffer_controles.clear()
            flush_buf()

        return filas3

    def _shell_scroll_formulario(self, hijos_columna: list) -> ft.Container:
        """Envuelve la columna principal del formulario en scroll sin duplicar nesting en el llamador."""
        content_column = ft.Container(
            content=ft.Column(hijos_columna, expand=True), expand=True, padding=0
        )
        return ft.Container(
            content=ft.Column([content_column], expand=True, scroll=ft.ScrollMode.AUTO),
            padding=0,
        )

    def _construir_contenido_dialogo(self, controles):
        """Arma mensaje, piezas opcionales (fideicomiso, tercero) y grid según `self.modo`."""
        filas = self._construir_filas_grid_formulario(controles)
        contenido_columna = self._bloques_superiores_dialogo()
        contenido_columna.append(self._fila_grid_centrada(filas))
        return self._shell_scroll_formulario(contenido_columna)

    def _fila_grid_centrada(self, filas: list[ft.Row]) -> ft.Row:
        """Centra el grid del formulario para mantener layout consistente entre modos."""
        grid = ft.Column(filas, spacing=0)
        return ft.Row([grid], alignment=ft.MainAxisAlignment.CENTER, expand=True)

    def _boton_selector_tercero(self) -> ft.Row:
        """Botón central para abrir selector de terceros en modo nuevo."""
        self._btn_selector_tercero = ft.Button(
            content="Seleccionar tercero",
            icon=ft.Icons.PERSON_SEARCH,
            style=BOTON_SECUNDARIO,
            on_click=lambda e: self._abrir_dialogo_hijo_con_carga(
                self._btn_selector_tercero,
                self._abrir_dialogo_terceros,
                "Abriendo selector de terceros...",
            ),
        )
        return ft.Row(
            [self._btn_selector_tercero], alignment=ft.MainAxisAlignment.CENTER
        )

    def _boton_editar_tercero(self) -> ft.Row:
        """Botón central para abrir edición del tercero actual."""
        self._btn_editar_tercero = ft.ElevatedButton(
            "Editar tercero",
            icon=ft.Icons.EDIT,
            style=BOTON_SECUNDARIO,
            on_click=lambda e: self._abrir_dialogo_hijo_con_carga(
                self._btn_editar_tercero,
                self._abrir_dialogo_editar_tercero,
                "Abriendo editor de tercero...",
            ),
        )
        return ft.Row(
            [self._btn_editar_tercero], alignment=ft.MainAxisAlignment.CENTER
        )

    def _bloques_superiores_dialogo(self) -> list:
        """Bloques superiores del diálogo antes del grid (mensajes, loaders, tarjetas y botones)."""
        mostrar_selector = self._debe_mostrar_selector_tercero()
        mostrar_boton_editar = self._debe_mostrar_boton_editar_tercero()
        mostrar_tarjeta_tercero = self._debe_mostrar_tarjeta_tercero()
        bloques = [self.mensaje]
        if self.modo == "fideicomiso_masivo":
            bloques.append(self.loader_fideicomiso)
            bloques.append(self._construir_filtros_fideicomiso())

        if mostrar_selector or mostrar_boton_editar:
            bloques.append(self.loader_apertura_tercero)

        if mostrar_selector:
            bloques.append(self._boton_selector_tercero())

        if mostrar_tarjeta_tercero:
            bloques.append(self._crear_tarjeta_tercero())
            if mostrar_boton_editar:
                bloques.append(self._boton_editar_tercero())

        if self.modo in ("nuevo", "editar") and not mostrar_tarjeta_tercero:
            tarjeta_contexto = self._crear_tarjeta_contexto_operativo()
            if tarjeta_contexto:
                bloques.append(tarjeta_contexto)
        return bloques

    def _construir_filtros_fideicomiso(self) -> ft.Container:
        """Dropdowns de filtro con valores ya existentes en hoja (sin duplicados)."""
        ex = self._mutar_hoja().obtener_valores_fideicomiso_existentes(self.concepto or {})
        self.filtro_tipo_actual = self._dropdown_filtro_fideicomiso(
            "Filtrar por tipo actual (opcional)",
            ex.get("tipo", []),
        )
        self.filtro_subtipo_actual = self._dropdown_filtro_fideicomiso(
            "Filtrar por subtipo actual (opcional)",
            ex.get("subtipo", []),
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Aplicar solo a registros que cumplan estos valores actuales (opcionales):",
                        size=12,
                        color=GREY_700,
                    ),
                    ft.Row([self.filtro_tipo_actual, self.filtro_subtipo_actual], spacing=6),
                ],
                spacing=4,
            ),
            padding=ft.padding.only(left=9, right=9, top=4, bottom=8),
        )

    def _valores_unicos_no_vacios(self, valores: list) -> list[str]:
        """Normaliza valores y elimina duplicados preservando orden."""
        return list(dict.fromkeys(str(v).strip() for v in valores if str(v).strip()))

    def _dropdown_filtro_fideicomiso(self, label: str, valores: list) -> DropdownCompact:
        """Construye un dropdown de filtro compacto para fideicomiso masivo."""
        opciones = [ft.DropdownOption(key=v, text=v) for v in self._valores_unicos_no_vacios(valores)]
        etiqueta_visible = str(label or "").strip()
        return DropdownCompact(
            label=etiqueta_visible,
            options=opciones,
            value=None,
            width=236,
            expand=False,
            tooltip=label,
        )

    def _padre_catalogo_dependiente(self, attr: str) -> str | None:
        """
        Clave en `self.datos` del atributo padre si este catálogo (CLASE=2 / TABLA=attr)
        está enlazado a otro por HIJOS en DATOSESPECIFICOS; si no hay relación, None.
        """
        key = (attr or "").strip()
        if not key or not self._es_clase_atributo(attr, 2):
            return None
        if key in self._cache_padre_catalogo:
            return self._cache_padre_catalogo[key]
        raw = None
        try:
            raw = self._datos_uc.obtener_tabla_padre_para_catalogo_dependiente(key)
        except Exception:
            raw = None
        resolved = self._resolver_clave_datos_case_insensitive(raw)
        self._cache_padre_catalogo[key] = resolved
        return resolved

    def _resolver_clave_datos_case_insensitive(self, raw_key: object) -> str | None:
        """Resuelve una clave de `self.datos` tolerando variaciones de mayúsculas/minúsculas."""
        if not raw_key:
            return None
        key_texto = str(raw_key).strip()
        if not key_texto:
            return None
        if key_texto in self.datos:
            return key_texto
        key_lower = key_texto.lower()
        for clave in self.datos:
            if clave.lower() == key_lower:
                return clave
        return None

    def _dropdown_options_desde_catalogo(self, opciones: list[dict]) -> list[ft.DropdownOption]:
        """Mapea opciones crudas de datos específicos a `DropdownOption`."""
        return [
            ft.DropdownOption(
                key=str(opcion["codigo"]),
                text=(opcion["descripcion"] or str(opcion["codigo"])).strip(),
            )
            for opcion in opciones
        ]

    def _opciones_catalogo_por_attr(self, attr: str, parent_attr: str | None = None, parent_valor: str | None = None) -> list[dict]:
        """Obtiene opciones de catálogo para un atributo, con o sin dependencia de padre."""
        tabla = (attr or "").strip()
        return self._opciones_dropdown_catalogo(tabla, parent_attr, parent_valor)

    def _dropdown_datos_especificos(self, attr: str) -> DropdownCompact:
        # TABLA en DATOSESPECIFICOS = ATRIBUTOS.DESCRIPCION (la etiqueta `attr`).
        parent_attr = self._padre_catalogo_dependiente(attr)
        parent_valor = self.datos.get(parent_attr, "") if parent_attr else None
        opciones = self._opciones_catalogo_por_attr(attr, parent_attr, parent_valor)
        opts = self._dropdown_options_desde_catalogo(opciones)
        v = str(self.datos.get(attr, "") or "").strip() or None
        de_lbl = str(attr or "").strip()
        return DropdownCompact(
            label=de_lbl,
            options=opts,
            value=v,
            width=self._ancho_control(attr),
            expand=False,
            tooltip=attr,
        )

    def _enlazar_tipos_con_subtipos(self):
        """Tras armar el grid: el padre (catálogo clase 2) dispara refresco del dependiente."""
        for attr in self.campos:
            p = self._padre_catalogo_dependiente(attr)
            if not p:
                continue
            parent_ctrl = self.campos.get(p)
            if not parent_ctrl:
                continue
            prev = getattr(parent_ctrl, "_on_select", None)

            def _make_handler(child_attr: str, previous):
                def _wrapped(e):
                    if previous:
                        previous(e)
                    self._actualizar_opciones_subtipo(child_attr)

                return _wrapped

            parent_ctrl._on_select = _make_handler(attr, prev)

    def _opciones_dropdown_catalogo(
        self, tabla: str, parent_attr: str | None = None, parent_valor: str | None = None
    ) -> list:
        """Obtiene opciones de catálogo simple o dependiente según exista padre."""
        if not tabla:
            return []
        if parent_attr:
            return self._datos_uc.obtener_opciones_datos_especificos(
                tabla, parent_attr, parent_valor
            )
        return self._datos_uc.obtener_opciones_datos_especificos(tabla)

    def _actualizar_opciones_subtipo(self, attr: str, limpiar_seleccion_hijo: bool = True):
        p = self._padre_catalogo_dependiente(attr)
        parent_ctrl, child_ctrl = self.campos.get(p), self.campos.get(attr)
        if not p or not parent_ctrl or not child_ctrl:
            return
        pv = self._key_from_label(parent_ctrl.value) if parent_ctrl.value else None
        opciones = self._opciones_catalogo_por_attr(attr, p, pv)
        child_ctrl.options = self._dropdown_options_desde_catalogo(opciones)
        if limpiar_seleccion_hijo:
            child_ctrl.value = None
        else:
            val = str(self.datos.get(attr, "") or "").strip()
            keys_ok = {str(o.key) for o in child_ctrl.options}
            child_ctrl.value = val if val in keys_ok else None
        self.page.update()
    
    def _crear_dialogo(self, contenido):
        """Crea el diálogo con título y acciones."""
        titulo = self._obtener_titulo_dialogo()
        btn = ft.Button(
            content=self._obtener_texto_boton_principal(),
            style=BOTON_PRINCIPAL,
            on_click=self._on_confirmar
        )
        self._btn_confirmar_dialogo = btn

        return ft.AlertDialog(
            modal=False,
            bgcolor=WHITE,
            title=ft.Text(titulo),
            content=contenido,
            shadow_color=PINK_200,
            elevation=15,
            actions=[
                ft.TextButton("Cancelar", on_click=self.cerrar, style=BOTON_SECUNDARIO_SIN),
                btn
            ],
        )

    def _debe_mostrar_selector_tercero(self) -> bool:
        """Indica si se debe mostrar el botón para seleccionar tercero."""
        return self.modo == "nuevo"

    def _debe_mostrar_tarjeta_tercero(self) -> bool:
        """Indica si se debe mostrar la tarjeta con datos del tercero."""
        return self.modo in ("nuevo", "editar") and bool(self.tercero_actual)

    def _debe_mostrar_boton_editar_tercero(self) -> bool:
        """En modo nuevo se selecciona; editar tercero aplica solo en edición."""
        return self.modo == "editar" and bool(self.tercero_actual)

    def _obtener_titulo_dialogo(self) -> str:
        """Misma longitud de título que en nuevo para que el AlertDialog no se ensanche solo en editar."""
        if self.modo == "fideicomiso_masivo":
            return "Asignar tipo/subtipo de fideicomiso"
        return (
            "Editar registro hoja de trabajo"
            if self.modo == "editar"
            else "Nuevo registro hoja de trabajo"
        )

    def _obtener_texto_boton_principal(self) -> str:
        """Devuelve el texto del botón principal según el modo."""
        if self.modo == "fideicomiso_masivo":
            return "Aplicar"
        return "Guardar" if self.modo == "editar" else "Crear"
    
    def _inicializar_dropdowns_dependientes(self):
        """Inicializa los dropdowns que dependen de otros valores."""
        for attr, ctrl in self.campos.items():
            upper_k = attr.upper()
            if ("PAÍS" in upper_k or "PAÃ" in upper_k or "PAIS" in upper_k) and ctrl.value:
                try:
                    self._llenar_departamentos_por_pais_label(ctrl.value)
                except Exception:
                    pass
                break
        for attr in self.campos.keys():
            parent_attr = self._padre_catalogo_dependiente(attr)
            if not parent_attr:
                continue
            pc = self.campos.get(parent_attr)
            if pc and pc.value:
                try:
                    self._actualizar_opciones_subtipo(
                        attr, limpiar_seleccion_hijo=False
                    )
                except Exception:
                    pass
    
    def _texto_resumen(self, valor) -> str:
        """Normaliza valores para tarjetas (tercero / resumen): vacío → "—", sin ocultar ceros."""
        if valor is None:
            return "—"
        if isinstance(valor, str) and not valor.strip():
            return "—"
        return str(valor).strip()

    def _fila_tarjeta_info(self, etiqueta: str, texto: str, ancho_etiqueta: int = 130) -> ft.Row:
        """Fila label + valor para tarjetas de solo lectura; `ancho_etiqueta` alinea con el diseño de cada tarjeta."""
        return ft.Row(
            [
                ft.Text(f"{etiqueta}:", weight=ft.FontWeight.BOLD, width=ancho_etiqueta),
                ft.Text(texto, expand=True),
            ],
            spacing=5,
        )

    def _partir_filas_tarjeta_dos_columnas(self, filas: list[ft.Row]) -> ft.Row:
        """Reparte filas info en dos columnas (primera mitad izquierda, resto derecha)."""
        n = len(filas)
        mitad = (n + 1) // 2
        col_izq = ft.Column(filas[:mitad], spacing=6, tight=True, expand=True)
        col_der = ft.Column(filas[mitad:], spacing=6, tight=True, expand=True)
        return ft.Row(
            [col_izq, col_der],
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    def _crear_tarjeta_tercero(self):
        """
        Tarjeta con datos del tercero seleccionado o cargado.
        Muestra siempre cada fila (vacío → "—"); el dígito 0 no se oculta (antes `if valor` lo escondía).
        """
        t = self.tercero_actual or {}
        campos: list[ft.Row] = []

        def fila(label: str, texto: str) -> None:
            campos.append(self._fila_tarjeta_info(label, texto))

        fila("Id", self._texto_resumen(t.get("id")))
        fila("Razón social", self._texto_resumen(t.get("razonsocial")))

        tipodoc = t.get("tipodocumento")
        if tipodoc is not None and str(tipodoc).strip():
            td_txt = obtener_nombre_tipodoc(tipodoc) or str(tipodoc).strip()
        else:
            td_txt = self._texto_resumen(tipodoc)
        fila("Tipo documento", td_txt)

        fila("Identidad", self._texto_resumen(t.get("identidad")))
        fila("Dígito verificación", self._texto_resumen(t.get("digitoverificacion")))

        fila("Primer nombre", self._texto_resumen(t.get("primernombre")))
        fila("Segundo nombre", self._texto_resumen(t.get("segundonombre")))
        fila("Primer apellido", self._texto_resumen(t.get("primerapellido")))
        fila("Segundo apellido", self._texto_resumen(t.get("segundoapellido")))

        fila("Dirección", self._texto_resumen(t.get("direccion")))

        pais_nom = obtener_nombre_pais(t.get("pais")) or "" if t.get("pais") else ""
        depto_nom = obtener_nombre_departamento(t.get("departamento")) or "" if t.get("departamento") else ""
        muni_nom = obtener_nombre_municipio(t.get("municipio"), t.get("departamento")) or "" if t.get("municipio") else ""
        ubicacion = ", ".join(filter(None, [muni_nom, depto_nom, pais_nom]))
        fila("Ubicación", ubicacion if ubicacion else "—")

        naturaleza = t.get("naturaleza")
        if naturaleza is None:
            fila("Naturaleza", "—")
        else:
            # TERCEROS.NATURALEZA: 0 = jurídica, 1 = natural (según obtener_terceros).
            try:
                es_natural = int(naturaleza) == 1
            except (TypeError, ValueError):
                es_natural = False
            fila("Naturaleza", "P. natural" if es_natural else "P. jurídica")

        _ya = {
            "id",
            "razonsocial",
            "tipodocumento",
            "identidad",
            "digitoverificacion",
            "primernombre",
            "segundonombre",
            "primerapellido",
            "segundoapellido",
            "direccion",
            "departamento",
            "municipio",
            "pais",
            "naturaleza",
        }
        for clave in sorted(t.keys()):
            if clave in _ya:
                continue
            fila(str(clave).replace("_", " "), self._texto_resumen(t.get(clave)))

        return ft.Container(
            content=self._partir_filas_tarjeta_dos_columnas(campos),
            padding=12,
            bgcolor=ft.Colors.GREY_100,
            border_radius=8,
            border=ft.border.all(1, PINK_200),
        )

    def _campos_resumen_clase_cero(self) -> list[tuple[str, str]]:
        """
        Construye pares (atributo, valor) desde el registro actual (`self.datos`) para
        atributos CLASE=0 del concepto. Solo incluye campos con valor real.
        """
        excluir_fijos = {"Concepto", "FORMATO", "id_concepto"}
        out: list[tuple[str, str]] = []
        def _norm(s: object) -> str:
            return str(s or "").strip().upper()

        lista_campos = self._obtener_atributos_concepto()

        # Catálogo de atributos permitidos en tarjeta (solo CLASE=0).
        clase_cero_por_norm: dict[str, str] = {}
        for campo in lista_campos:
            if len(campo) < 5:
                continue
            descripcion = str(campo[2] or "").strip()
            if not descripcion or descripcion in excluir_fijos:
                continue
            clase = campo[3] or 0
            try:
                es_clase_cero = int(clase) == 0
            except (TypeError, ValueError):
                es_clase_cero = str(clase).strip() == "0"
            if not es_clase_cero:
                continue

            desc_upper = _norm(descripcion)
            if "CONCEPTO" in desc_upper and "CODIGO" in desc_upper:
                continue

            clase_cero_por_norm.setdefault(desc_upper, descripcion)

        # Orden base: el del esquema del formulario, para mantener consistencia visual.
        orden_norm: dict[str, int] = {}
        idx = 0
        for attr in self._orden_campos_formulario():
            n = _norm(attr)
            if n and n not in orden_norm:
                orden_norm[n] = idx
                idx += 1

        for clave, valor in self.datos.items():
            clave_txt = str(clave or "").strip()
            if not clave_txt or clave_txt in excluir_fijos:
                continue
            clave_norm = _norm(clave_txt)
            if clave_norm not in clase_cero_por_norm:
                continue

            valor_txt = self._texto_resumen(valor)
            if valor_txt == "—":
                continue

            etiqueta = clase_cero_por_norm.get(clave_norm, clave_txt)
            out.append((etiqueta, valor_txt))

        # Deduplicar por etiqueta final y ordenar por el orden natural del concepto.
        dedup: dict[str, str] = {}
        for k, v in out:
            dedup[k] = v
        return sorted(
            dedup.items(),
            key=lambda kv: (orden_norm.get(_norm(kv[0]), 10_000), _norm(kv[0])),
        )

    def _crear_tarjeta_resumen(self, titulo: str, campos: list[tuple[str, str]]) -> ft.Control | None:
        """Tarjeta reusable para mostrar pares atributo/valor en dos columnas."""
        if not campos:
            return None

        filas: list[ft.Row] = [
            self._fila_tarjeta_info(label, texto, ancho_etiqueta=170) for label, texto in campos
        ]

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(titulo, weight=ft.FontWeight.W_600, color=GREY_700),
                    self._partir_filas_tarjeta_dos_columnas(filas),
                ],
                spacing=8,
            ),
            padding=12,
            bgcolor=ft.Colors.GREY_100,
            border_radius=8,
            border=ft.border.all(1, PINK_200),
        )

    def _crear_tarjeta_contexto_operativo(self) -> ft.Control | None:
        """
        Tarjeta contextual para atributos CLASE=0 del concepto.
        Incluye todos los atributos de la clase, tengan o no valor.
        """
        campos_clase_cero = self._campos_resumen_clase_cero()
        return self._crear_tarjeta_resumen("Información contextual", campos_clase_cero)

    # ==================== DIÁLOGO DE ELIMINACIÓN ====================
    
    def _atributos_valor_opciones_filtro_eliminar(self) -> list[tuple]:
        """Pares (id_atributo, descripción) de atributos CLASE valor (tipo 1) para filtro opcional."""
        campos = self._obtener_atributos_concepto()
        return [(a[0], a[1]) for a in campos if a[2] == 1]

    def _on_opcion_eliminar_change(self, e):
        """Muestra u oculta identidad según radio de alcance."""
        self.input_identidad.visible = self.opcion.value == "identidad"
        self.page.update()

    def _abrir_dialogo_eliminar(self):
        """
        Abre el diálogo para eliminar registros.
        Solo se usa cuando `abrir()` se invoca con modo='eliminar'.
        """
        self._btn_confirmar_dialogo = None
        opt = self._atributos_valor_opciones_filtro_eliminar()

        self.opcion = ft.RadioGroup(
            value="identidad",
            content=ft.Column([
                ft.Radio(value="identidad", label="Eliminar por Identidad", active_color=PINK_200),
                ft.Radio(value="concepto", label="Eliminar todo el Concepto", active_color=PINK_200)
            ])
        )

        self.input_identidad = ft.TextField(
            label="Identidad",
            visible=True,
            border_color=PINK_200,
            label_style=ft.TextStyle(color=GREY_700),
            max_length=20,
        )

        self.select_campo = DropdownCompact(
            label="Campo a evaluar",
            options=[ft.DropdownOption(key=f"{id_} | {desc}", text=f"{id_} | {desc}") for id_, desc in opt],
            expand=True,
        )

        self.input_filtro = ft.TextField(
            label="Si el valor es menor a",
            hint_text="Filtro opcional",
            keyboard_type=ft.KeyboardType.NUMBER,
            border_color=PINK_200,
            label_style=ft.TextStyle(color=GREY_700),
            max_length=20,
        )

        self.opcion.on_change = self._on_opcion_eliminar_change
        self.loader_eliminar = crear_loader_row("Eliminando registros...", size=SIZE_SMALL)
        self.loader_eliminar.visible = False
        content = ft.Column([
            ft.Text("Seleccione el tipo de eliminación", weight=ft.FontWeight.BOLD),
            self.opcion,
            self.input_identidad,
            ft.Text("Opcional: "),
            self.select_campo,
            self.input_filtro,
            self.loader_eliminar,
        ], tight=True)
        
        self.dialog = ft.AlertDialog(
            title=ft.Text("Eliminar registros"),
            content=content,
            bgcolor=WHITE,
            actions=[
                ft.TextButton("Cancelar", on_click=self.cerrar, style=BOTON_SECUNDARIO_SIN),
                ft.Button(content="Eliminar", on_click=self._confirmar_eliminacion, style=BOTON_PRINCIPAL)
            ]
        )
        
        self.page.show_dialog(self.dialog)
    
    def _confirmar_eliminacion(self, e):
        """Confirma y ejecuta la eliminación."""
        campo_label = self.select_campo.value
        campo_id = self._key_from_label(campo_label) if campo_label else None
        filtro = float(self.input_filtro.value) if self.input_filtro.value else None
        opcion = self.opcion.value
        if opcion == "identidad":
            identidad = self.input_identidad.value.strip()
            if not identidad:
                return
        concepto = self.concepto

        loader_row_visibilidad(self.page, self.loader_eliminar, True)
        def _worker():
            try:
                if opcion == "identidad":
                    self._mutar_hoja().eliminar_hoja_por_identidad(
                        identidad=identidad, filtro=filtro, campo_id=campo_id
                    )
                else:
                    self._mutar_hoja().eliminar_hoja_por_concepto(
                        concepto=concepto, filtro=filtro, campo_id=campo_id
                    )
            finally:
                loader_row_fin(self.page, self.loader_eliminar)
                self.cerrar()
                self.parent.cargar_datos()
                self.page.update()
        self.page.run_thread(_worker)

    # ==================== MANEJO DE DROPDOWNS DEPENDIENTES ====================
    
    def _llenar_departamentos_por_pais_label(self, pais_label):
        """Llena el dropdown de departamentos basado en el país seleccionado."""
        if not self.drop_dep:
            return
        
        pais_key = self._key_from_label(pais_label)
        deps_iter = [(k, v[0]) for k, v in DEPARTAMENTOS.items() if str(v[1]) == str(pais_key)]
        
        opts = []
        selected_value = None
        desc_depto = self._obtener_descripcion_atributo("departamento")
        valor_actual = self.datos.get(desc_depto) if desc_depto else None
        
        for k, name in deps_iter:
            label_txt = self._label(k, name)
            opts.append(ft.DropdownOption(key=label_txt, text=label_txt))
            if valor_actual and str(valor_actual) == str(k):
                selected_value = label_txt
                if selected_value:
                    self._llenar_municipios_por_departamento_label(label_txt)
        
        self.drop_dep.options = opts
        self.drop_dep.value = selected_value
    
    def _llenar_municipios_por_departamento_label(self, dept_label):
        """Llena el dropdown de municipios basado en el departamento seleccionado."""
        if not self.drop_mun:
            return
        
        dept_key = self._key_from_label(dept_label)
        dept_key_int = int(dept_key) if str(dept_key).isdigit() else None
        
        muns_iter = [
            (v[0], v[1]) for _, v in MUNICIPIOS.items()
            if (dept_key_int and int(v[2]) == dept_key_int) or str(v[2]) == str(dept_key)
        ]
        
        opts = []
        selected_value = None
        desc_muni = self._obtener_descripcion_atributo("municipio")
        valor_actual = self.datos.get(desc_muni) if desc_muni else None
        
        for codigo, name in muns_iter:
            label_txt = self._label(codigo, name)
            opts.append(ft.DropdownOption(key=label_txt, text=label_txt))
            if valor_actual and str(valor_actual) == str(codigo):
                selected_value = label_txt
        
        self.drop_mun.options = opts
        self.drop_mun.value = selected_value
    
    def _on_pais_change(self, e):
        """Maneja el cambio de país."""
        self._llenar_departamentos_por_pais_label(e.control.value)
        if self.drop_dep:
            self.drop_dep.value = None
        if self.drop_mun:
            self.drop_mun.options = []
            self.drop_mun.value = None
        self.page.update()
    
    def _on_departamento_change(self, e):
        """Maneja el cambio de departamento."""
        self._llenar_municipios_por_departamento_label(e.control.value)
        if self.drop_mun:
            self.drop_mun.value = None
        self.page.update()

    # ==================== DIÁLOGOS DE TERCEROS ====================
    def _set_apertura_tercero_ocupada(self, ocupado: bool, texto: str = "Abriendo..."):
        """Muestra carga de apertura para feedback inmediato en flujos de tercero."""
        if self.loader_apertura_tercero:
            self.loader_apertura_tercero.visible = ocupado
            if self.loader_apertura_tercero.controls and len(self.loader_apertura_tercero.controls) > 1:
                self.loader_apertura_tercero.controls[1].value = f" {texto}"
        if self._btn_selector_tercero:
            self._btn_selector_tercero.disabled = ocupado
        if self._btn_editar_tercero:
            self._btn_editar_tercero.disabled = ocupado

    def _abrir_dialogo_hijo_con_carga(self, control_boton: ft.Control | None, accion, texto_carga: str):
        """Pinta estado ocupado antes de abrir un diálogo hijo para evitar sensación de congelamiento."""
        if control_boton:
            control_boton.disabled = True
        self._set_apertura_tercero_ocupada(True, texto_carga)
        self.page.update()
        loop = self.page.session.connection.loop
        loop.call_later(0.05, accion)
    
    def _abrir_dialogo_terceros(self):
        """
        Abre el catálogo de terceros para seleccionar uno.
        Solo se muestra y usa en modo 'nuevo'.
        """
        self._cerrar_dialogo_actual_para_hijo()
        self.tercero_dialog.open_agregar_dialog()
    
    def _abrir_dialogo_editar_tercero(self):
        """
        Abre el diálogo de edición del tercero actual.
        Solo está disponible en modo 'editar' cuando hay un tercero cargado.
        """
        tercero = self.tercero_actual.copy()
        self._cerrar_dialogo_actual_para_hijo()
        self.tercero_dialog_editar.abrir(tercero=tercero, origen="editar")

    def _cerrar_dialogo_actual_para_hijo(self) -> None:
        """Guarda referencia y cierra el diálogo actual antes de abrir uno hijo."""
        self.dialog_trabajo_guardado = self.dialog
        if not self.dialog:
            return
        self.page.pop_dialog()
        self.page.update()

    def _valor_desde_control_grid(self, attr: str, ctrl) -> object:
        """Interpreta `value` del control del grid según etiqueta/key o atributo monetario."""
        val = getattr(ctrl, "value", None)
        if not val:
            return ""
        if self._control_usa_key_from_label(ctrl):
            return self._key_from_label(val)
        if self._es_atributo_valor(attr):
            return self._normalizar_valor_monetario(val)
        return val

    def _valores_desde_controles_solo_grid(self) -> dict:
        """Lee solo atributos que tienen control en el grid (excluye tercero)."""
        datos: dict = {}
        for attr, ctrl in self.campos.items():
            tipoacumulado = self.atributos_info.get(attr, 0)
            if self._es_campo_de_tercero(tipoacumulado, attr):
                continue
            datos[attr] = self._valor_desde_control_grid(attr, ctrl)
        return datos

    def _fusionar_campos_tercero_desde_datos(self, datos: dict) -> None:
        """Añade a `datos` los valores de tercero que viven en `self.datos` (no están en el grid)."""
        for attr, tipoacumulado in self.atributos_info.items():
            if self._es_campo_de_tercero(tipoacumulado, attr):
                datos[attr] = str(self.datos.get(attr, "") or "")

    def _recopilar_datos_formulario(self):
        """Recopila grid + valores de tercero almacenados en self.datos (tarjeta / selección)."""
        datos = self._valores_desde_controles_solo_grid()
        self._fusionar_campos_tercero_desde_datos(datos)
        return datos
