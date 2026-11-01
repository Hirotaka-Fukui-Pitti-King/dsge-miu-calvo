"""Verify all reported benchmark moments against the committed simulation data."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKS = {
    ("technology", "flex", "Выпуск"): 0.01337225,
    ("technology", "calvo", "Выпуск"): 0.01249910,
    ("technology", "flex", "Инвестиции"): 0.05470091,
    ("technology", "calvo", "Инвестиции"): 0.04947752,
    ("monetary", "calvo", "Выпуск"): -0.00431472,
    ("monetary", "calvo", "Инвестиции"): -0.02274988,
    ("monetary", "calvo", "Потребление"): 0.00017552,
    ("monetary", "calvo", "Труд"): -0.00643988,
}


def rows(shock: str, regime: str) -> list[dict[str, str]]:
    with (ROOT / "results" / f"otkliki_{shock}_{regime}.csv").open(
        newline="", encoding="utf-8-sig"
    ) as stream:
        result = list(csv.DictReader(stream))
    if len(result) != 41 or [int(x["Период"]) for x in result] != list(range(41)):
        raise AssertionError("The IRF horizon is not 0–40 quarters.")
    return result


def main() -> None:
    for (shock, regime, variable), expected in CHECKS.items():
        observed = float(rows(shock, regime)[0][variable])
        if abs(observed - expected) > 6e-8:
            raise AssertionError(f"Reported value inconsistent: {shock}/{regime}/{variable}")
    for variable in ("Выпуск", "Потребление", "Инвестиции", "Труд", "Капитал"):
        if max(abs(float(row[variable])) for row in rows("monetary", "flex")) > 1e-9:
            raise AssertionError(f"Monetary neutrality check failed for {variable}.")
    print("Paper's numerical claims and monetary neutrality verified against the CSVs.")


if __name__ == "__main__":
    main()
