# Evals

Miden las funciones con IA: calidad, latencia, tokens y costo. Las funciones deterministas se prueban solo con pytest y no llevan evals.

| Comando | Qué hace |
|---|---|
| `uv run python evals/correr.py` | Corre todas las suites. |
| `uv run python evals/correr.py --suite NOMBRE` | Corre una suite. |
| `uv run --env-file .env python evals/correr.py` | Corre con los secretos de `.env`. |

## Suites y casos

Cada suite conecta un archivo de casos con una función del proyecto en [`config.toml`](config.toml) ([decisión 0001](../docs/decisiones/0001-arnes-de-evals.md)):

```toml
[suites.my_function]
casos = "casos/my_function.jsonl"
funcion = "app.my_module:my_function"
umbral = 0.9   # fracción mínima de casos aprobados
```

Cada línea de `evals/casos/*.jsonl` es un caso. La función recibe `entrada` como único argumento.

```json
{"id": "caso-01", "entrada": "...", "esperado": "...", "calificacion": "exacta"}
{"id": "caso-02", "entrada": "...", "esperado": 12.5, "calificacion": "numerica", "tolerancia": 0.01}
```

- **`exacta`:** la salida debe ser el mismo valor JSON que `esperado`. Los decimales se comparan por su valor exacto, así que 12.5 = 12.50 y un `Decimal` cuenta como número, pero 2 ≠ 2.0 y `true` ≠ 1. Un valor que no es JSON, como `date`, reprueba: devuelve las fechas como texto ISO.
- **`numerica`:** la diferencia absoluta debe ser ≤ `tolerancia`. Se calcula en `Decimal`.
- `esperado` y `tolerancia` se leen como `Decimal`, sin pasar por float; `entrada` llega a la función con los tipos normales de JSON.
- Puedes agregar claves para documentar el caso, como `nota`.

## Resultados

Cada corrida imprime un resumen y guarda `evals/resultados/<suite>-AAAAMMDD-HHMMSS.csv` con las columnas `id, aprobado, latencia_ms, esperado, obtenido, error, modelo, tokens_entrada, tokens_salida, costo_usd`. El costo se calcula en `Decimal` con [`precios.toml`](precios.toml) ([decisión 0002](../docs/decisiones/0002-registro-de-uso-y-costo.md)).

Códigos de salida:

| Código | Significado |
|---|---|
| 0 | Todas las suites cumplen su umbral, o no hay suites que correr. |
| 1 | Alguna suite no cumple su umbral. |
| 2 | La configuración o los casos están mal formados, o el módulo de una función no se puede importar. |

## Agregar una función con IA

1. Escribe sus casos en `evals/casos/<nombre>.jsonl`.
2. Agrega su bloque en `evals/config.toml`.
3. Elige una ruta para llamar al modelo (abajo) y, después de cada llamada, reporta los tokens con [`record_usage`](../src/app/usage.py). Fuera de los evals, `record_usage` no hace nada.
4. Si el modelo no está en `evals/precios.toml`, agrégalo en USD por millón de tokens. Sin precio, el costo sale vacío.

### Dos rutas para llamar al modelo

Ningún proyecto queda obligado a una.

| | API de Anthropic | `claude -p` (Claude Code headless) |
|---|---|---|
| Credencial | `ANTHROPIC_API_KEY` en `.env` | La sesión iniciada de Claude Code, sin API key |
| Pago | Por token | La suscripción |
| Costo del CSV | Exacto | Cota superior |
| CI | Funciona | No sirve: necesita una sesión iniciada |

**API de Anthropic.** Pide `ANTHROPIC_API_KEY` y se paga por token. El costo del CSV es exacto y funciona en CI. Después de cada respuesta:

```python
from app.usage import record_usage

record_usage(response.model, response.usage.input_tokens, response.usage.output_tokens)
```

**`claude -p`.** Usa la suscripción, sin API key. El costo del CSV es una cota superior, porque `precios.toml` no modela la caché ([decisión 0002](../docs/decisiones/0002-registro-de-uso-y-costo.md)) y los tokens de caché se cuentan a precio normal. Necesita `claude` en el PATH con una sesión iniciada, así que no sirve en CI. Lecciones de un proyecto que ya lo usa:

- **`--output-format stream-json`** (con `-p` exige `--verbose`). El último evento, de tipo `result`, trae `modelUsage`: un objeto por modelo con `inputTokens`, `cacheReadInputTokens`, `cacheCreationInputTokens` y `outputTokens`. Llama a `record_usage` una vez por modelo, con la suma de los tres primeros como entrada.
- **`--setting-sources ""`**: sin tus ajustes. El estilo de salida personal se colaba en las respuestas.
- **`--tools ""`**: sin las herramientas integradas de Claude Code.
- **Un directorio de trabajo vacío** (por ejemplo, uno temporal), para que no cargue el `CLAUDE.md` del proyecto.
- **Quita `ANTHROPIC_API_KEY` del entorno del proceso**, para que nunca use la API por accidente.

```bash
claude -p "PREGUNTA" --output-format stream-json --verbose --setting-sources "" --tools "" --no-session-persistence
```

**Cómo elegir.** Si los evals corren en CI, si la función va a producción o si necesitas el costo exacto, usa la API. Para evals personales con la suscripción, usa `claude -p`. Anota la elección en un ADR del proyecto (copia [`0000-plantilla.md`](../docs/decisiones/0000-plantilla.md)).
