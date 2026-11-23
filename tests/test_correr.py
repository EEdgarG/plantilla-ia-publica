from datetime import date
from decimal import Decimal

import pytest

from app.usage import Usage, record_usage
from evals import correr

PRICES = {"modelo-a": {"entrada": Decimal("3"), "salida": Decimal("15")}}


def exact_case(expected):
    return {"id": "c1", "entrada": None, "esperado": expected, "calificacion": "exacta"}


def numeric_case(expected, tolerance):
    return {
        "id": "c1", "entrada": None, "esperado": expected,
        "calificacion": "numerica", "tolerancia": tolerance,
    }


@pytest.mark.parametrize(
    ("expected", "actual", "passed"),
    [
        ("WALMEX", "WALMEX", True),
        ({"a": 1, "b": [1, 2]}, {"b": (1, 2), "a": 1}, True),  # orden de claves y tupla = lista
        ("WALMEX", "walmex", False),
        (2, 2.0, False),
        (1, True, False),
        (Decimal("12.50"), 12.5, True),  # así llega un 12.50 leído del JSONL
        (Decimal("2.0"), 2.0, True),
        (2, Decimal("2.0"), False),
        ({"monto": Decimal("12.5")}, {"monto": Decimal("12.50")}, True),  # un Decimal cuenta como número
        (Decimal("0.10000000000000000001"), 0.1, False),
        ("12.5", Decimal("12.5"), False),  # texto contra número
        ("2026-10-09", date(2026, 10, 9), False),  # un valor que no es JSON reprueba
    ],
)
def test_exact_grading_compares_as_json(expected, actual, passed):
    assert correr.grade(exact_case(expected), actual) is passed


@pytest.mark.parametrize(
    ("actual", "passed"),
    [
        (10.0, True),
        (10.01, True),
        (9.99, True),
        (Decimal("10.005"), True),
        (10.02, False),
        (True, False),
        ("10", False),
        (float("nan"), False),
    ],
)
def test_numeric_grading_uses_absolute_tolerance(actual, passed):
    assert correr.grade(numeric_case(10.0, 0.01), actual) is passed


def test_numeric_grading_boundary_is_exact():
    assert abs(1.1 - 1.0) > 0.1  # con float, el borde de la tolerancia reprobaría
    assert correr.grade(numeric_case(1.0, 0.1), 1.1) is True


def test_compute_cost_is_an_exact_decimal():
    usages = [Usage("modelo-a", 1_000, 500), Usage("modelo-a", 200, 100)]
    # (1 200 × 3 + 600 × 15) / 1 000 000
    assert correr.compute_cost(usages, PRICES) == Decimal("0.0126")


def test_compute_cost_is_unknown_without_usage_or_price():
    assert correr.compute_cost([], PRICES) is None
    assert correr.compute_cost([Usage("sin-precio", 10, 10)], PRICES) is None


def test_run_case_records_errors_without_stopping():
    def fails(_):
        raise ValueError("clave vacía")

    result = correr.run_case(fails, exact_case("X"), PRICES)
    assert result.passed is False
    assert result.error == "ValueError: clave vacía"


def test_run_case_collects_usage_and_cost():
    def echo(text):
        record_usage("modelo-a", 1_000, 0)
        return text

    result = correr.run_case(echo, {**exact_case("hola"), "entrada": "hola"}, PRICES)
    assert result.passed is True
    assert result.cost == Decimal("0.003")


def test_resolve_function_reports_import_failures_as_config_errors(tmp_path, monkeypatch):
    (tmp_path / "broken_module.py").write_text("def f(:\n", encoding="utf-8")
    monkeypatch.syspath_prepend(tmp_path)
    with pytest.raises(correr.EvalError, match="SyntaxError"):
        correr.resolve_function("broken_module:f")


def test_resolve_function_requires_an_existing_function():
    with pytest.raises(correr.EvalError, match="no tiene una función"):
        correr.resolve_function("app.usage:missing")


def test_load_cases_keeps_expected_precision(tmp_path):
    path = tmp_path / "casos.jsonl"
    path.write_text(
        '{"id": "a", "entrada": 0.5, "esperado": 0.10000000000000000001,'
        ' "calificacion": "numerica", "tolerancia": 0}\n',
        encoding="utf-8",
    )
    [case] = correr.load_cases(path)
    assert case["esperado"] == Decimal("0.10000000000000000001")  # con float sería 0.1
    assert correr.grade(case, Decimal("0.1")) is False
    assert type(case["entrada"]) is float  # la función recibe los tipos normales de JSON


def test_exact_grading_still_accepts_decimal_literals(tmp_path):
    path = tmp_path / "casos.jsonl"
    path.write_text('{"id": "a", "entrada": null, "esperado": 12.50, "calificacion": "exacta"}\n', encoding="utf-8")
    [case] = correr.load_cases(path)
    assert correr.run_case(lambda _: 12.5, case, PRICES).passed is True


@pytest.mark.parametrize("config", ["", "[suites]\n"])
def test_main_without_suites_exits_with_0(tmp_path, monkeypatch, capsys, config):
    (tmp_path / "config.toml").write_text(config, encoding="utf-8")
    (tmp_path / "precios.toml").write_text("", encoding="utf-8")
    monkeypatch.setattr(correr, "EVALS_DIR", tmp_path)
    assert correr.main([]) == 0
    assert "no hay suites que correr" in capsys.readouterr().out


@pytest.mark.parametrize("config", ["suites = 5\n", "[suites.rota]\ncasos = 1\n"])
def test_main_with_malformed_config_exits_with_2(tmp_path, monkeypatch, config):
    (tmp_path / "config.toml").write_text(config, encoding="utf-8")
    (tmp_path / "precios.toml").write_text("", encoding="utf-8")
    monkeypatch.setattr(correr, "EVALS_DIR", tmp_path)
    assert correr.main([]) == 2


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        (['{"id": "a", "entrada": 1, "esperado": 1}'], "faltan claves"),
        (['{"id": "a", "entrada": 1, "esperado": 1, "calificacion": "aprox"}'], "calificacion"),
        (['{"id": "a", "entrada": 1, "esperado": 1, "calificacion": "numerica"}'], "tolerancia"),
        (['{"id": "a", "entrada": 1, "esperado": 1, "calificacion": "exacta"}'] * 2, "id repetido"),
        (["no es json"], "JSON inválido"),
    ],
)
def test_load_cases_reports_file_and_line(tmp_path, lines, message):
    path = tmp_path / "casos.jsonl"
    path.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(correr.EvalError, match=message) as error:
        correr.load_cases(path)
    assert f"{path}:{len(lines)}:" in str(error.value)
