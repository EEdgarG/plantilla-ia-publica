"""Registro de los tokens que usan las funciones con IA.

Una función que llama a un modelo invoca ``record_usage`` después de cada
llamada a la API y devuelve su valor normal. Fuera de ``collect_usage`` el
registro no hace nada, así que en producción no cuesta; evals/correr.py
envuelve cada caso en ``collect_usage`` para sumar tokens y calcular el costo
(docs/decisiones/0002).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class Usage:
    model: str
    input_tokens: int
    output_tokens: int


_records: ContextVar[list[Usage] | None] = ContextVar("usage_records", default=None)


def record_usage(model: str, input_tokens: int, output_tokens: int) -> None:
    """Anota el uso de una llamada al modelo si hay una recolección activa."""
    records = _records.get()
    if records is not None:
        records.append(Usage(model, input_tokens, output_tokens))


@contextmanager
def collect_usage() -> Iterator[list[Usage]]:
    """Junta en una lista el uso que se registre dentro del bloque ``with``."""
    records: list[Usage] = []
    token = _records.set(records)
    try:
        yield records
    finally:
        _records.reset(token)
