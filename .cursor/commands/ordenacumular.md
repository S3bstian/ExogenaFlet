# Comando: Ordenar y Actualizar Función Acumular

## Objetivo
Leer la tabla `FORMAACUMULADO` de la base de datos y modificar la función `acumular_conceptos_hoja_trabajo` en `infrastructure/repositories/firebird/acumulacion_hoja_trabajo.py` para generar automáticamente el bloque `match attr[1]:` con todos los casos ordenados alfabéticamente.

## Pasos a Ejecutar

### 1. Leer la Tabla FormaAcumulado
- Usar la función existente `obtener_forma_acumulado()` en `infrastructure/persistence/firebird/elementos_atributos_persistencia.py`, pasando a la conexión el código de empresa `-2` cuando aplique
- Obtener los campos que expone `obtener_forma_acumulado()`: `Id`, `Nombre`, `Descripcion`, `Mostrar_cuentas`, `Global`
- La consulta en código es equivalente a: `SELECT Id, Nombre, Descripcion, Mostrar_cuentas, Global`

### 2. Procesar y Agrupar los Datos
- **Agrupar IDs por descripción semántica similar**: Analizar las descripciones y agrupar IDs que se refieren al mismo concepto (ej: "Tipo de Documento", "Número de Identificación", "Razón Social", "Primer Apellido", etc.)
- **Identificar similitudes**: Si una descripción contiene palabras clave similares a otra, agruparlas (ej: "Código del País" y "País" deben estar juntos)
- **Mantener casos especiales separados**:
  - ID 1001: Concepto (caso especial, sin verificar elemento[1])
  - ID 50: Acumulado para activos fijos (solo para tipo 'A')

### 3. Modificar la Función `acumular_conceptos_hoja_trabajo`
- **Ubicación**: `infrastructure/repositories/firebird/acumulacion_hoja_trabajo.py`, función `acumular_conceptos_hoja_trabajo`
- **Reemplazar**: El bloque completo `match attr[1]:` dentro del loop de atributos
- **Estructura de cada case**:
  ```python
  # ==================== [DESCRIPCION EN MAYÚSCULAS] ====================
  # IDs: id1, id2, id3, ...
  case x if x in (id1, id2, id3, ...):
      if elemento[1] == 'T':
          valor = setdatos[indice]  # comentario descriptivo
      elif elemento[1] == 'C':
          valor = setdatos[indice]  # comentario descriptivo
      elif elemento[1] == 'B':
          valor = setdatos[indice]  # comentario descriptivo
      elif elemento[1] == 'A':
          valor = setdatos[indice]  # comentario descriptivo
      else:
          valor = "No ha acumulado"
  ```

### 4. Lectura de setdatos por Ejecución

El comando debe enlazar los valores del `match attr[1]:` leyendo el `setdatos` real en tiempo de ejecución.

- Para cada tipo (`T`, `C`, `B`, `A`), tomar como referencia el `SELECT` que arma `setdatos` en esa rama.
- Enlazar cada acumulado con los campos que realmente estén en ese `setdatos`.
- Si un campo no existe para ese tipo o no viene en el set, usar `valor = "No ha acumulado ID={attr[1]}, Desc='{attr[3]}'"`.
- Mantener agrupación semántica, orden alfabético, casos especiales y `case _`.

### 5. Casos Especiales

#### ID 1001 - Concepto:
```python
case 1001:
    valor = concepto.get("codigo")
```
- No verificar `elemento[1]`, siempre usar el código del concepto

#### ID 50 - Acumulado para activos fijos:
```python
case 50:
    if elemento[1] == 'A':
        valor = setdatos[0] if len(setdatos) > 0 else "No ha acumulado ID={attr[1]}, Desc='{attr[3]}'"  # Codigo
    else:
        valor = "No ha acumulado ID={attr[1]}, Desc='{attr[3]}'"
```
- Solo disponible para tipo 'A'

### 6. Reglas de Agrupación por Descripción

Agrupar IDs que tengan descripciones semánticamente relacionadas:
- **"Tipo de Documento"**: Agrupar todos los IDs relacionados con tipos de documento
- **"Número de Identificación"**: Agrupar IDs de identificación, NIT, cédula, etc.
- **"Razón Social"**: Agrupar razón social, nombre comercial, etc.
- **"Primer Apellido"**: Agrupar primer apellido y variantes
- **"Segundo Apellido"**: Agrupar segundo apellido y variantes
- **"Primer Nombre"**: Agrupar primer nombre y variantes
- **"Otros Nombres"**: Agrupar segundos nombres, otros nombres, etc.
- **"Dirección"**: Agrupar dirección, dirección completa, etc.
- **"Departamento"**: Agrupar departamento y código de departamento
- **"Municipio"**: Agrupar municipio y código de municipio
- **"País"**: Agrupar país y código de país
- **"Saldo inicial"**: Agrupar saldo inicial y variantes
- **"Débitos"**: Agrupar débitos y variantes
- **"Créditos"**: Agrupar créditos y variantes
- **"Neto"**: Agrupar neto y variantes
- **"Saldo final"**: Agrupar saldo final y variantes

### 7. Orden Alfabético
- Ordenar todos los cases alfabéticamente por la descripción principal
- Ignorar artículos como "El", "La", "Los", "Las" al ordenar
- El caso especial (1001) debe ir después de "CONCEPTO" alfabéticamente
- El caso por defecto (`case _:`) siempre al final

### 8. Manejo de Campos No Disponibles
- Si un campo no está disponible para un tipo de elemento específico, asignar `valor = "No ha acumulado ID={attr[1]}, Desc='{attr[3]}'"` **SIN hacer print**
- Solo el caso por defecto (no mapeado) debe mostrar un warning, y solo cada 500 iteraciones para no saturar la consola:
  ```python
  case _:
      valor = "No ha acumulado"
      if (i + 1) % 500 == 0:  # Solo cada 500 para no saturar
          print(f"    [WARNING] Caso no mapeado - ID: {attr[1]}, Desc: {attr[3][:30]}..., Tipo: {elemento[1]}")
  ```

### 9. Validaciones y Consideraciones
- **No eliminar prints de progreso existentes**: Mantener los prints de `[CONCEPTO]`, `[ELEMENTO]`, `[ATRIBUTOS]`, `[INSERTS]` que ya existen
- **Mantener la estructura del código**: No modificar la lógica de loops, solo el bloque `match attr[1]:`
- **Comentarios descriptivos**: Cada case debe tener un comentario con la descripción en mayúsculas y la lista de IDs
- **Lectura dinámica obligatoria**: Verificar en cada ejecución que el enlace del `match` coincide con el `setdatos` real generado por su `SELECT`
- **Grupo `GLOBAL` en `FORMAACUMULADO`**: El dropdown de configuración de atributo filtra por la columna `GLOBAL` (`T/C/B/A`) frente al tipo global del elemento; no hay rangos por `Id`. Si cambian grupos o IDs, basta con mantener `GLOBAL` correcto en BD y el contrato de `obtener_forma_acumulado()`.

### 10. Ejecución
1. Leer la tabla `FORMAACUMULADO` usando `obtener_forma_acumulado()`
2. Procesar y agrupar los datos por descripción semántica
3. Generar el código del bloque `match attr[1]:` completo
4. Reemplazar el bloque existente en `acumular_conceptos_hoja_trabajo`
5. Verificar que no haya errores de sintaxis
6. Mostrar un resumen de:
   - Total de IDs procesados
   - Total de grupos creados
   - Casos especiales identificados
   - Cambios realizados

## Notas Importantes
- La función debe mantener la compatibilidad con el código existente
- No modificar la lógica de obtención de datos, solo el mapeo de atributos
- Mantener el orden alfabético estricto para facilitar el mantenimiento futuro
- Todo el cambio debe ser hecho sin usar scripts ni escribir codigo aparte para crear lo que pido, esto debe ser un cambio hecho por la maquina IA
- el valor de _no no lo cambia ni la salida _ del match
- Tipos (`C`, `B`, `A`) nunca tienen atributos "Primer Apellido","Segundo Apellido","Primer Nombre", "Otros Nombres" y relacionados, sus cases dejaran vacio ("")
