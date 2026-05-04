"""
Funciones de validación y manejo de errores en controles.
"""
from typing import Optional, Tuple, Callable, Any


def validar_numero(
    valor: Any, tipo: str = "float", min_val: Optional[float] = None, max_val: Optional[float] = None
) -> Tuple[bool, Optional[str]]:
    """
    Valida que un valor sea un número válido del tipo especificado.
    Returns (True, None) si es válido, (False, mensaje_error) si no lo es.
    """
    if valor is None or str(valor).strip() == "":
        return True, None

    valor_str = str(valor).strip()
    try:
        num_val = int(valor_str) if tipo == "int" else float(valor_str)
        if min_val is not None and num_val < min_val:
            return False, f"El valor debe ser mayor o igual a {min_val}"
        if max_val is not None and num_val > max_val:
            return False, f"El valor debe ser menor o igual a {max_val}"
        return True, None
    except ValueError:
        tipo_nombre = "entero" if tipo == "int" else "número"
        return False, f"Debe ser un {tipo_nombre} válido"


def validar_fecha(valor: Any) -> Tuple[bool, Optional[str]]:
    """Valida formato YYYY-MM-DD."""
    if not valor or str(valor).strip() == "":
        return True, None

    valor_str = str(valor).strip()
    partes = valor_str.split("-")
    if len(partes) != 3:
        return False, "Formato de fecha inválido. Use YYYY-MM-DD"

    try:
        from calendar import isleap

        año, mes, dia = int(partes[0]), int(partes[1]), int(partes[2])
        if año < 1900 or año > 9999:
            return False, "El año debe estar entre 1900 y 9999"
        if mes < 1 or mes > 12:
            return False, "El mes debe estar entre 1 y 12"
        if dia < 1 or dia > 31:
            return False, "El día debe estar entre 1 y 31"
        dias_por_mes = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        if isleap(año):
            dias_por_mes[1] = 29
        if dia > dias_por_mes[mes - 1]:
            return False, f"El día {dia} no es válido para el mes {mes}"
        return True, None
    except ValueError:
        return False, "Formato de fecha inválido. Use YYYY-MM-DD"


def validar_hora(valor: Any) -> Tuple[bool, Optional[str]]:
    """Valida formato HH:MM:SS."""
    if not valor or str(valor).strip() == "":
        return True, None

    valor_str = str(valor).strip()
    partes = valor_str.split(":")
    if len(partes) != 3:
        return False, "Formato de hora inválido. Use HH:MM:SS"

    try:
        hh, mm, ss = int(partes[0]), int(partes[1]), int(partes[2])
        if hh < 0 or hh > 23:
            return False, "Las horas deben estar entre 00 y 23"
        if mm < 0 or mm > 59:
            return False, "Los minutos deben estar entre 00 y 59"
        if ss < 0 or ss > 59:
            return False, "Los segundos deben estar entre 00 y 59"
        return True, None
    except ValueError:
        return False, "Formato de hora inválido. Use HH:MM:SS"


def validar_email(valor: Any) -> Tuple[bool, Optional[str]]:
    """Valida formato de email básico."""
    if not valor or str(valor).strip() == "":
        return True, None

    valor_str = str(valor).strip()
    if "@" not in valor_str:
        return False, "El email debe contener el símbolo @"
    partes = valor_str.split("@")
    if len(partes) != 2:
        return False, "Formato de email inválido"
    local, dominio = partes[0], partes[1]
    if not local or not local.strip():
        return False, "El email debe tener una parte local antes del @"
    if not dominio or not dominio.strip():
        return False, "El email debe tener un dominio después del @"
    if "." not in dominio:
        return False, "El dominio del email debe contener al menos un punto"
    return True, None


def validar_campo_obligatorio(valor: Any, nombre_campo: str = "campo") -> Tuple[bool, Optional[str]]:
    """Valida que un campo obligatorio no esté vacío."""
    if valor is None:
        return False, f"{nombre_campo} es obligatorio"
    if str(valor).strip() == "":
        return False, f"{nombre_campo} es obligatorio"
    return True, None


def validar_identidad_documento_numerica(
    valor: Any, nombre_campo: str = "Número de documento"
) -> Tuple[bool, Optional[str]]:
    """Documento obligatorio y solo dígitos (sin letras ni símbolos)."""
    if valor is None or str(valor).strip() == "":
        return False, f"{nombre_campo} es obligatorio"
    s = str(valor).strip()
    if not s.isdigit():
        return False, f"{nombre_campo} debe contener solo números"
    return True, None


def validar_digito_verificacion_opcional(valor: Any) -> Tuple[bool, Optional[str]]:
    """Dígito de verificación vacío permitido; si tiene valor, solo 1–2 dígitos."""
    if valor is None or str(valor).strip() == "":
        return True, None
    s = str(valor).strip()
    if not s.isdigit() or len(s) > 2:
        return False, "Use solo números (1 o 2 dígitos)"
    return True, None


def set_campo_error(control: Any, mensaje: Optional[str]) -> None:
    """Asigna mensaje de error en un control (error/error_text según corresponda)."""
    if control is None:
        return
    if hasattr(control, "error"):
        control.error = mensaje
    if hasattr(control, "error_text"):
        control.error_text = mensaje
    if hasattr(control, "update"):
        try:
            control.update()
        except Exception:
            pass


def aplicar_validacion_error_text(
    control: Any, valor: Any, funcion_validacion: Callable, *args, nombre_campo: Optional[str] = None, **kwargs
) -> bool:
    """Aplica validación y muestra error en el control. Retorna True si es válido."""
    kwargs_call = dict(kwargs)
    if nombre_campo is not None:
        kwargs_call["nombre_campo"] = nombre_campo
    es_valido, mensaje = funcion_validacion(valor, *args, **kwargs_call)
    set_campo_error(control, mensaje if not es_valido else None)
    return es_valido
