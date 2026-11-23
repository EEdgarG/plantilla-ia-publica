# 0002: Tokens con record_usage y costo en Decimal

- **Fecha:** 2026-10-09
- **Estado:** aceptada

## Contexto
`evals/correr.py` reporta tokens y costo cuando la función los reporta. El costo es un monto, así que se calcula en código con los precios de `evals/precios.toml`, nunca con el modelo (CLAUDE.md). Una función con IA puede hacer varias llamadas por caso: reintentos, pasos encadenados o varios modelos.

## Opciones consideradas
1. **`record_usage()` sobre un `ContextVar`.** La función llama `record_usage(modelo, tokens_entrada, tokens_salida)` después de cada llamada a la API y devuelve su valor normal. `collect_usage()` junta los registros de un bloque `with`; fuera de él, `record_usage` no hace nada.
2. **Devolver un `ModelResult(value, model, input_tokens, output_tokens)`.** Explícito y sin estado global, pero el código de producción tiene que leer `.value`, y si hay varias llamadas el uso se suma a mano.
3. **Devolver una tupla `(valor, uso)`.** Lo más corto, pero no se distingue de una función que devuelve una tupla de verdad.

## Decisión
Opción 1, en `src/app/usage.py`. El costo de un caso es Σ(tokens_entrada × precio.entrada + tokens_salida × precio.salida) / 1 000 000. Los precios están en USD por millón de tokens y se leen como `Decimal` con `tomllib.load(..., parse_float=Decimal)`. Si algún modelo no tiene precio, el costo queda vacío y se muestra un aviso: nunca se reporta un costo parcial.

## Consecuencias
- Las funciones con IA devuelven tipos normales (`str`, `dict`), y sus pruebas no cambian.
- Reintentos, llamadas encadenadas y varios modelos se suman solos.
- Si una función no llama a `record_usage`, el CSV muestra tokens vacíos, no ceros, así que la omisión se nota.
- El costo es exacto: no hay errores de redondeo de float.

## Qué dato la haría cambiar
- Usar caché de prompts, modo rápido o precios por tramo (Claude Haiku 5.5 arriba de 100K tokens): cobran distinto y habría que agregar campos a `Usage` y a `precios.toml`.
- Hacer llamadas en hilos: un `ContextVar` no pasa a un hilo nuevo sin `contextvars.copy_context()`.
