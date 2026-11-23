# Plantilla IA

Plantilla para proyectos de software con IA. Cada proyecto empieza con una especificación aprobada, registra sus decisiones y mide sus funciones con IA con evals: calidad, latencia, tokens y costo.

Incluye un ejemplo que no llama a ninguna API, `normalize_ticker`, que normaliza claves de pizarra de la BMV (`" walmex * "` → `"WALMEX"`). Sirve para probar todo de punta a punta; bórralo al crear un proyecto.

| Archivo | Para qué |
|---|---|
| `docs/spec.md` | Qué construimos y cómo sabremos que funciona. Se llena antes de escribir código. |
| `docs/decisiones/` | Una decisión de arquitectura por archivo, con las opciones descartadas. Copia `0000-plantilla.md`. |
| `docs/bitacora.md` | Una entrada por paso o decisión, la más reciente arriba: qué decidí, por qué, qué falló, evidencia y prompts importantes. |
| `evals/` | Casos, configuración de suites, precios por modelo y resultados. Cómo usarlos: [evals/README.md](evals/README.md). |
| `src/app/` | Código del proyecto. `usage.py` registra tokens para los evals. |

## Crear un proyecto desde la plantilla

1. En GitHub, abre la plantilla y usa **Use this template** → **Create a new repository**. Luego clona el repo nuevo:
   ```bash
   git clone https://github.com/TU-USUARIO/mi-proyecto.git && cd mi-proyecto
   ```
   Sin GitHub: `rsync -a --exclude .git --exclude .venv plantilla-ia/ mi-proyecto/` y `git init` dentro de `mi-proyecto`.
2. En `pyproject.toml`, cambia `name` y `description`. El paquete se llama `app` en todos los proyectos, así que no hay que renombrar nada más ([decisión 0003](docs/decisiones/0003-estructura-del-paquete.md)).
3. Borra el ejemplo y sus resultados:
   ```bash
   rm src/app/example_tickers.py tests/test_example_tickers.py evals/casos/example_tickers.jsonl
   rm -rf evals/resultados   # correr.py la vuelve a crear
   ```
   Luego quita el bloque `[suites.example_tickers]` de `evals/config.toml`.
4. Reescribe este README para tu proyecto: qué hace, cómo se usa y sus comandos. Conserva la lista de terminado y borra esta sección, «Crear un proyecto».
5. Instala con `uv sync`.
6. Llena `docs/spec.md` y cambia su estado a «aprobada» antes de escribir código. Claude Code no escribe código mientras la spec esté en borrador o tenga secciones vacías (ver `CLAUDE.md`).

## Comandos

| Qué | Comando |
|---|---|
| Instalar | `uv sync` |
| Pruebas | `uv run pytest` |
| Una prueba | `uv run pytest tests/test_archivo.py::test_nombre` |
| Evals, todas las suites | `uv run python evals/correr.py` |
| Evals, una suite | `uv run python evals/correr.py --suite NOMBRE` |
| Con los secretos de `.env` | `uv run --env-file .env python evals/correr.py` |

Copia `.env.example` a `.env` para tus claves. `.env` no se versiona.

## Evals

Cómo configurar suites, escribir casos, leer el CSV y agregar una función con IA, incluidas las dos rutas para llamar al modelo: [evals/README.md](evals/README.md).

## Lista de terminado

Un proyecto está terminado cuando tiene:

- [ ] **Problema y decisión:** `docs/spec.md` completo y cada decisión de arquitectura en `docs/decisiones/`.
- [ ] **Pruebas:** `uv run pytest` pasa.
- [ ] **Evals con resultados:** si hay funciones con IA, `uv run python evals/correr.py` cumple el umbral, y su CSV está en `evals/resultados/`.
- [ ] **Costo medido:** si hay funciones con IA, la columna `costo_usd` está llena, con precios vigentes y fechados en `evals/precios.toml`.
- [ ] **Qué falló y por qué:** está anotado en `docs/bitacora.md`, junto con los casos fallidos de las pruebas o del CSV.

Las funciones deterministas se prueban solo con pytest: no llevan evals ni costo.

## Licencia

[MIT](LICENSE).
