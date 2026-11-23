# 0003: Paquete `app` en src/, instalado con uv_build

- **Fecha:** 2026-10-09
- **Estado:** aceptada

## Contexto
Las pruebas y `evals/correr.py` importan el código del proyecto. Como esto es una plantilla, cada proyecto nace de una copia, y cada nombre que haya que cambiar en cada copia es una oportunidad de error.

## Opciones consideradas
1. **Paquete genérico `src/app/`, instalado en modo editable por `uv_build`.** No hay nada que renombrar: las pruebas y `evals/config.toml` importan `app` igual en todos los proyectos.
2. **Paquete con el nombre de cada proyecto** (`src/mi_proyecto/`). Es la convención de `uv init --package`, pero cada copia exige renombrar la carpeta, `pyproject.toml`, los imports y `evals/config.toml`.
3. **Sin backend de construcción.** Una dependencia menos, pero `correr.py` tendría que modificar `sys.path` para encontrar el código.

## Decisión
Opción 1, con `[tool.uv.build-backend] module-name = "app"` en `pyproject.toml`. `uv_build` es el backend de uv: solo se usa al construir, no en ejecución, y permite que `uv sync` instale `app` en el entorno.

## Consecuencias
- Crear un proyecto solo pide cambiar `name` y `description` en `pyproject.toml`.
- Todos los proyectos importan `app`, así que dos de ellos no caben en el mismo entorno. No es un problema, porque cada uno tiene su `.venv`.

## Qué dato la haría cambiar
- Publicar un proyecto como librería en PyPI: ahí el paquete necesita un nombre único.
