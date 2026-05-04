"""
Manejo de fechas Helisa.
"""
from calendar import isleap


def fechaHelisa(pAno: int, pMes: int, pDia: int) -> int:
    """
    Retorna un entero que representa una fecha helisa.
    pAno: Año. pMes: Mes. pDia: Día.
    """
    dias_periodo = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31, 31, 31]
    if pAno < 1 or pAno > 9999:
        raise Exception("Año fuera de rango")
    if pMes < 0 or pMes > 14:
        raise Exception("Mes fuera de rango")
    if isleap(pAno):
        dias_periodo[1] = 29
    if pDia < 1 or pDia > dias_periodo[pMes - 1]:
        raise Exception("Día fuera de rango")
    diasPeriodo = pDia + sum(dias_periodo[: pMes - 1])
    pAno = pAno - 1
    return pAno * 427 + pAno // 4 - pAno // 100 + pAno // 400 + diasPeriodo - 811332
