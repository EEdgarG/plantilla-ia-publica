"""Ejemplo de la plantilla: normaliza claves de pizarra de la BMV.

No llama a ninguna API; existe para probar pytest y evals/correr.py de punta a
punta. Por eso, aunque es determinista, tiene casos de eval: es la excepción a
la regla de CLAUDE.md. Bórralo al crear un proyecto (ver README.md).
"""


def normalize_ticker(raw: str) -> str:
    """Normaliza una clave de pizarra (emisora y serie) a mayúsculas.

    - Quita los espacios de los extremos y junta los repetidos.
    - Quita la serie ``*``, con o sin espacio antes: " walmex * " → "WALMEX".
    - Conserva las demás series: "amx b" → "AMX B", "funo 11" → "FUNO 11".
    - Lanza ValueError si no queda clave: "", "   ", "*".
    """
    without_series = raw.replace("*", "")
    ticker = " ".join(without_series.split()).upper()
    if not ticker:
        raise ValueError(f"Clave de pizarra vacía: {raw!r}")
    return ticker
