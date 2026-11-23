import pytest

from app.example_tickers import normalize_ticker


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" walmex * ", "WALMEX"),
        ("walmex*", "WALMEX"),
        ("walmex\t*", "WALMEX"),
        ("WALMEX", "WALMEX"),
        ("amx b", "AMX B"),
        ("  gfnorte   o  ", "GFNORTE O"),
        ("funo 11", "FUNO 11"),
        ("pe&oles *", "PE&OLES"),
        ("livepol c-1", "LIVEPOL C-1"),
    ],
)
def test_normalize_ticker(raw, expected):
    assert normalize_ticker(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "*", " * "])
def test_normalize_ticker_rejects_empty_keys(raw):
    with pytest.raises(ValueError):
        normalize_ticker(raw)


def test_normalize_ticker_is_idempotent():
    once = normalize_ticker(" gfnorte   o ")
    assert normalize_ticker(once) == once
