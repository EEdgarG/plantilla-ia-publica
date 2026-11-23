# 0001: Arnés de evals con suites en config.toml

- **Fecha:** 2026-10-09
- **Estado:** aceptada

## Contexto
Las funciones que llaman a un modelo de IA llevan casos en `evals/casos/` (CLAUDE.md) y se miden de forma repetible. La plantilla necesita un solo comando, `uv run python evals/correr.py`, que califique cada función contra sus casos, mida latencia, tokens y costo, y deje evidencia en un CSV. Un proyecto puede tener varias funciones con IA, así que el comando necesita saber qué función corre contra qué casos y con qué umbral.

## Opciones consideradas
1. **`evals/config.toml` con un bloque por suite** (`casos`, `funcion`, `umbral`). Toda la configuración de evals vive en `evals/`, y agregar o borrar una suite es tocar un bloque.
2. **`[tool.evals]` en `pyproject.toml`.** Un archivo menos, pero la configuración queda lejos de sus casos y mezclada con la del paquete.
3. **Encabezado en cada JSONL**: la primera línea declara la función y el umbral. Cada suite cabe en un archivo, pero el archivo mezcla dos formatos de línea.
4. **Solo argumentos de terminal.** Flexible, pero sin argumentos el comando no sabría qué correr, y el umbral no quedaría escrito en ningún lado.

## Decisión
Opción 1, con estas reglas:
- Los casos son JSONL con claves en español (`id`, `entrada`, `esperado`, `calificacion`, `tolerancia`), igual que la spec. Los identificadores de Python siguen en inglés.
- La función recibe `entrada` como único argumento.
- `esperado` y `tolerancia` se leen como `Decimal` (`parse_float=Decimal`) para calificar sin pasar por float; `entrada` llega a la función con los tipos normales de JSON.
- `exacta` compara salida y esperado como valores JSON, con los decimales por su valor exacto (12.5 = 12.50, y un `Decimal` cuenta como número), pero 2 ≠ 2.0 y `true` ≠ 1; un valor que no es JSON, como `date`, reprueba. `numerica` acepta una diferencia absoluta de hasta `tolerancia`, calculada en `Decimal`.
- Una excepción reprueba el caso sin detener la corrida.
- Cada corrida escribe un CSV por suite en `evals/resultados/`. Los CSV se versionan como evidencia.
- Código de salida: 0 si todas las suites cumplen su umbral o si no hay suites que correr, 1 si alguna no lo cumple, 2 si la configuración o los casos están mal formados, incluido un módulo que falla al importarse.
- Solo usa la biblioteca estándar.

## Consecuencias
- Agregar una función con IA es escribir su JSONL y su bloque en `config.toml`.
- El código de salida permite usar el comando como verificación automática, por ejemplo antes de un commit.
- La calificación es determinista: todavía no hay forma de calificar respuestas abiertas.
- Los CSV versionados se acumulan; los viejos se borran a mano.

## Qué dato la haría cambiar
- Necesitar calificar texto libre (por ejemplo, con un modelo como juez) o casos que esperan un error.
- Que la tolerancia absoluta no sirva porque los valores cambian mucho de escala; entonces haría falta una tolerancia relativa.
