# Instrucciones del proyecto

Qué construimos y cómo sabremos que funciona: @docs/spec.md

## Flujo de trabajo
- No escribas código sin una especificación aprobada en docs/spec.md, es decir, con la línea de estado en «aprobada». Si tiene secciones vacías, pregúntame antes de seguir.
- La spec describe lo vigente: cuando algo cambia, actualiza su sección y anota el cambio, con su porqué, en docs/bitacora.md.
- Si el cambio toca más de un archivo, propón un plan antes de editar.
- Las funciones que llaman a un modelo de IA llevan casos en evals/casos/; las funciones deterministas se prueban solo con pytest.
- Registra en docs/decisiones/ solo decisiones de arquitectura (estructura, dependencias, almacenamiento, interfaces); las reglas de negocio van en docs/spec.md. Copia `0000-plantilla.md` y numera en orden.
- Registra cada paso o decisión en docs/bitacora.md, la entrada más reciente arriba, con lo que falló y la evidencia.
- Cuando dejes un `TODO(human)` y yo responda “listo”, lee el archivo: ya lo edité.
- Al terminar, muestra evidencia: los comandos que corriste y su salida.

## Comandos
- Instalar: `uv sync`
- Pruebas: `uv run pytest`
- Una prueba: `uv run pytest tests/test_archivo.py::test_nombre`
- Evals: `uv run python evals/correr.py`

## Reglas
- Python con uv; no uses pip directamente.
- Secretos solo en .env; documenta las variables en .env.example.
- Montos, saldos y fechas se calculan en código, nunca con el modelo.
- No agregues dependencias sin explicar por qué.
- Documentación en español; código, nombres y commits en inglés. Las claves de los datos (JSONL, CSV, TOML) también van en español.
