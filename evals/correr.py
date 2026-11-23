"""Corre las suites de evals/config.toml contra las funciones del proyecto.

Uso:
    uv run python evals/correr.py                  # todas las suites
    uv run python evals/correr.py --suite NOMBRE   # solo una

Por cada suite califica sus casos, guarda un CSV en evals/resultados/ e imprime
un resumen. Sale con 0 si todas las suites cumplen su umbral (o si no hay
suites que correr), 1 si alguna no lo cumple y 2 si la configuración o los
casos están mal formados. Formato de los casos y columnas del CSV: README.md.
Decisiones: docs/decisiones/0001 y 0002.
"""

import argparse
import csv
import importlib
import json
import statistics
import sys
import time
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.usage import Usage, collect_usage

EVALS_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVALS_DIR / "resultados"
GRADINGS = ("exacta", "numerica")
CSV_COLUMNS = [
    "id", "aprobado", "latencia_ms", "esperado", "obtenido", "error",
    "modelo", "tokens_entrada", "tokens_salida", "costo_usd",
]
TOKENS_PER_PRICE = 1_000_000  # precios.toml está en USD por millón de tokens

Prices = dict[str, dict[str, Decimal]]


class EvalError(Exception):
    """Error en la configuración o en los casos; detiene la corrida con código 2."""


@dataclass
class Suite:
    name: str
    function_spec: str
    function: Callable[[Any], Any]
    cases: list[dict[str, Any]]
    threshold: Decimal


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    latency_ms: float
    expected: Any
    actual: Any
    error: str
    usages: list[Usage]
    cost: Decimal | None


# --- Carga y validación -----------------------------------------------------


def load_toml(path: Path) -> dict[str, Any]:
    """Lee un TOML con los decimales como Decimal, sin pasar por float."""
    try:
        with path.open("rb") as file:
            return tomllib.load(file, parse_float=Decimal)
    except FileNotFoundError:
        raise EvalError(f"{path}: no existe") from None
    except tomllib.TOMLDecodeError as exc:
        raise EvalError(f"{path}: TOML inválido: {exc}") from None


def load_prices(path: Path) -> Prices:
    """Lee precios.toml: USD por millón de tokens de entrada y de salida, por modelo."""
    prices: Prices = {}
    for model, entry in load_toml(path).get("modelos", {}).items():
        entry = entry if isinstance(entry, dict) else {}
        input_price = _as_finite_decimal(entry.get("entrada"))
        output_price = _as_finite_decimal(entry.get("salida"))
        if input_price is None or output_price is None or min(input_price, output_price) < 0:
            raise EvalError(f"{path}: el modelo {model!r} necesita 'entrada' y 'salida' numéricos >= 0")
        prices[model] = {"entrada": input_price, "salida": output_price}
    return prices


def load_suites(path: Path, only: str | None = None) -> list[Suite]:
    """Lee config.toml y carga los casos y la función de cada suite (o solo de `only`).

    Si no hay suites devuelve una lista vacía: no es un error de configuración.
    """
    configured = load_toml(path).get("suites", {})
    if not isinstance(configured, dict):
        raise EvalError(f"{path}: [suites] debe ser una tabla")
    if only is not None:
        if only not in configured:
            available = ", ".join(sorted(configured)) or "ninguna"
            raise EvalError(f"no existe la suite {only!r} (disponibles: {available})")
        configured = {only: configured[only]}
    suites = []
    for name, settings in configured.items():
        where = f"{path} [suites.{name}]"
        if not isinstance(settings, dict):
            raise EvalError(f"{where}: debe ser una tabla con 'casos', 'funcion' y 'umbral'")
        cases_file, function_spec = settings.get("casos"), settings.get("funcion")
        if not isinstance(cases_file, str) or not isinstance(function_spec, str):
            raise EvalError(f"{where}: 'casos' y 'funcion' deben ser texto")
        threshold = _as_finite_decimal(settings.get("umbral"))
        if threshold is None or not 0 <= threshold <= 1:
            raise EvalError(f"{where}: 'umbral' debe ser una fracción entre 0 y 1")
        suites.append(Suite(
            name=name,
            function_spec=function_spec,
            function=resolve_function(function_spec),
            cases=load_cases(path.parent / cases_file),
            threshold=threshold,
        ))
    return suites


def resolve_function(spec: str) -> Callable[[Any], Any]:
    """Importa la función que nombra un texto 'modulo:funcion'."""
    module_name, _, attribute = spec.partition(":")
    if not module_name or not attribute:
        raise EvalError(f"funcion {spec!r}: usa el formato 'modulo:funcion'")
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # cualquier fallo al importar es de configuración (código 2), no del umbral
        raise EvalError(
            f"funcion {spec!r}: no se pudo importar {module_name!r}: {type(exc).__name__}: {exc}"
        ) from None
    function = getattr(module, attribute, None)
    if not callable(function):
        raise EvalError(f"funcion {spec!r}: {module_name!r} no tiene una función {attribute!r}")
    return function


def load_cases(path: Path) -> list[dict[str, Any]]:
    """Lee y valida un JSONL de casos; cada error indica archivo:línea."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        raise EvalError(f"{path}: no existe") from None
    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        where = f"{path}:{number}"
        try:
            # esperado y tolerancia se califican sin pasar por float
            case = json.loads(line, parse_float=Decimal)
        except json.JSONDecodeError as exc:
            raise EvalError(f"{where}: JSON inválido: {exc.msg}") from None
        _validate_case(case, where)
        # la función recibe `entrada` con los tipos normales de JSON (json.dumps no acepta Decimal)
        case["entrada"] = json.loads(line)["entrada"]
        if case["id"] in seen_ids:
            raise EvalError(f"{where}: id repetido {case['id']!r}")
        seen_ids.add(case["id"])
        cases.append(case)
    if not cases:
        raise EvalError(f"{path}: no tiene casos")
    return cases


def _validate_case(case: Any, where: str) -> None:
    if not isinstance(case, dict):
        raise EvalError(f"{where}: cada línea debe ser un objeto JSON")
    missing = [key for key in ("id", "entrada", "esperado", "calificacion") if key not in case]
    if missing:
        raise EvalError(f"{where}: faltan claves: {', '.join(missing)}")
    if not isinstance(case["id"], str) or not case["id"]:
        raise EvalError(f"{where}: 'id' debe ser texto no vacío")
    if case["calificacion"] not in GRADINGS:
        raise EvalError(f"{where}: 'calificacion' debe ser 'exacta' o 'numerica'")
    if case["calificacion"] == "numerica":
        tolerance = _as_finite_decimal(case.get("tolerancia"))
        if tolerance is None or tolerance < 0:
            raise EvalError(f"{where}: un caso numérico necesita 'tolerancia' >= 0")
        if _as_finite_decimal(case["esperado"]) is None:
            raise EvalError(f"{where}: un caso numérico necesita un 'esperado' numérico")


# --- Calificación y costo ---------------------------------------------------


def grade(case: dict[str, Any], actual: Any) -> bool:
    """Califica la salida de un caso según su 'calificacion'."""
    if case["calificacion"] == "exacta":
        try:
            return _canonical_json(actual) == _canonical_json(case["esperado"])
        except (TypeError, ValueError):  # la salida no es JSON, p. ej. una fecha
            return False
    actual_number = _as_finite_decimal(actual)
    if actual_number is None:
        return False
    expected = _as_finite_decimal(case["esperado"])
    tolerance = _as_finite_decimal(case["tolerancia"])
    return abs(actual_number - expected) <= tolerance


def compute_cost(usages: list[Usage], prices: Prices) -> Decimal | None:
    """Costo en USD del uso de un caso; None si no hubo uso o falta algún precio."""
    if not usages or any(usage.model not in prices for usage in usages):
        return None
    total = sum(
        (
            usage.input_tokens * prices[usage.model]["entrada"]
            + usage.output_tokens * prices[usage.model]["salida"]
            for usage in usages
        ),
        start=Decimal(0),
    )
    return total / TOKENS_PER_PRICE


# --- Ejecución y reporte ----------------------------------------------------


def run_case(function: Callable[[Any], Any], case: dict[str, Any], prices: Prices) -> CaseResult:
    """Corre un caso midiendo latencia y uso; si la función truena, el caso reprueba."""
    actual, error = None, ""
    with collect_usage() as usages:
        start = time.perf_counter()
        try:
            actual = function(case["entrada"])
        except Exception as exc:  # un caso que truena reprueba, pero la corrida sigue
            error = type(exc).__name__ + (f": {exc}" if str(exc) else "")
        latency_ms = (time.perf_counter() - start) * 1000
    return CaseResult(
        case_id=case["id"],
        passed=not error and grade(case, actual),
        latency_ms=latency_ms,
        expected=case["esperado"],
        actual=actual,
        error=error,
        usages=usages,
        cost=compute_cost(usages, prices),
    )


def write_csv(results: list[CaseResult], path: Path) -> Path:
    """Guarda una fila por caso con las columnas de CSV_COLUMNS."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(_csv_row(result) for result in results)
    return path


def _csv_row(result: CaseResult) -> dict[str, Any]:
    usages = result.usages
    return {
        "id": result.case_id,
        "aprobado": "true" if result.passed else "false",
        "latencia_ms": f"{result.latency_ms:.3f}",
        "esperado": _as_json(result.expected),
        "obtenido": "" if result.error else _as_json(result.actual),
        "error": result.error,
        "modelo": "+".join(sorted({usage.model for usage in usages})),
        "tokens_entrada": sum(usage.input_tokens for usage in usages) if usages else "",
        "tokens_salida": sum(usage.output_tokens for usage in usages) if usages else "",
        "costo_usd": "" if result.cost is None else format(result.cost, "f"),
    }


def print_summary(suite: Suite, results: list[CaseResult], prices: Prices, csv_path: Path) -> bool:
    """Imprime el resumen de una suite y devuelve si cumplió su umbral."""
    passed = sum(result.passed for result in results)
    rate = Decimal(passed) / len(results)
    meets = rate >= suite.threshold
    latencies = [result.latency_ms for result in results]
    print(f"\n== {suite.name} · {suite.function_spec} ==")
    print(
        f"Aprobados: {passed}/{len(results)} ({rate:.1%}) · "
        f"umbral {suite.threshold:.1%} → {'CUMPLE' if meets else 'NO CUMPLE'}"
    )
    print(
        f"Latencia (ms): media {statistics.fmean(latencies):.3f} · "
        f"mediana {statistics.median(latencies):.3f} · máx {max(latencies):.3f}"
    )
    print(_usage_line(results, prices))
    failed = [result for result in results if not result.passed]
    print("Fallidos:" if failed else "Fallidos: ninguno")
    for result in failed:
        reason = result.error or f"obtenido {_as_json(result.actual)}, esperado {_as_json(result.expected)}"
        print(f"  - {result.case_id}: {reason}")
    print(f"CSV: {_display_path(csv_path)}")
    return meets


def _usage_line(results: list[CaseResult], prices: Prices) -> str:
    usages = [usage for result in results for usage in result.usages]
    if not usages:
        return "Tokens y costo: no reportados (la función no llama a record_usage)"
    tokens = (
        f"Tokens: {sum(usage.input_tokens for usage in usages):,} de entrada, "
        f"{sum(usage.output_tokens for usage in usages):,} de salida"
    )
    missing = sorted({usage.model for usage in usages} - prices.keys())
    if missing:
        return f"{tokens} · Costo: desconocido, falta precio en precios.toml para {', '.join(missing)}"
    total = sum((result.cost for result in results if result.cost is not None), start=Decimal(0))
    return f"{tokens} · Costo: US$ {total:.6f}"


# --- Utilidades -------------------------------------------------------------


def _as_finite_decimal(value: Any) -> Decimal | None:
    """Convierte un número de JSON, TOML o Python a Decimal; None si no es un número finito."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    number = value if isinstance(value, Decimal) else Decimal(str(value))
    return number if number.is_finite() else None


def _canonical_json(value: Any) -> str:
    """JSON estable para la calificación exacta: claves ordenadas y decimales por su valor exacto.

    12.5, 12.50 y Decimal("12.5") dan lo mismo, pero 2 y 2.0 no (entero contra decimal).
    Lanza TypeError si el valor no es JSON, por ejemplo una fecha.
    """
    if isinstance(value, (float, Decimal)):
        number = _as_finite_decimal(value)
        if number is None:
            raise TypeError(f"{value!r} no es un número finito")
        text = format(number.normalize(), "f")
        return text if "." in text else f"{text}.0"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_canonical_json(item) for item in value) + "]"
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("las claves de un objeto JSON deben ser texto")
        pairs = (
            f"{json.dumps(key, ensure_ascii=False)}: {_canonical_json(item)}"
            for key, item in sorted(value.items())
        )
        return "{" + ", ".join(pairs) + "}"
    return json.dumps(value, ensure_ascii=False)  # None, bool, int y str; lo demás lanza TypeError


def _as_json(value: Any) -> str:
    """Texto para el CSV y el resumen: JSON si se puede; si no, repr() para que se vea el tipo."""
    try:
        return _canonical_json(value)
    except (TypeError, ValueError):
        return repr(value)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Corre las suites de evals/config.toml.")
    parser.add_argument("--suite", help="corre solo esta suite")
    args = parser.parse_args(argv)
    try:
        suites = load_suites(EVALS_DIR / "config.toml", only=args.suite)
        prices = load_prices(EVALS_DIR / "precios.toml")
    except EvalError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if not suites:
        print("no hay suites que correr")
        return 0
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    all_meet = True
    for suite in suites:
        results = [run_case(suite.function, case, prices) for case in suite.cases]
        csv_path = write_csv(results, RESULTS_DIR / f"{suite.name}-{stamp}.csv")
        all_meet = print_summary(suite, results, prices, csv_path) and all_meet
    return 0 if all_meet else 1


if __name__ == "__main__":
    sys.exit(main())
