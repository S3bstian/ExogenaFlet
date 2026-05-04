"""
Periodo gravable y fechas inicial/final.
"""
from utils.dates import fechaHelisa

PERIODO: int = 2025
FECHA_INICIAL = fechaHelisa(PERIODO, 1, 1)
FECHA_FINAL = fechaHelisa(PERIODO, 12, 31)

# Mientras no exista el servicio de licencias de Helisa: no exige clave de activación real.
# Poner en False cuando el usuario deba ingresar la clave emitida por Helisa.
LICENCIA_MOCK_SIN_API: bool = True
# Cupo de empresas para pruebas cuando no hay servicio de licencias.
LICENCIA_MOCK_CUPO_EMPRESAS: int = 10
