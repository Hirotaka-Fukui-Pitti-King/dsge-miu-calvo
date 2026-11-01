"""Проверка происхождения и величин, приводимых в исследовательской статье."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

EXPECTED = {
    ("technology", "flex", "Выпуск"): 0.01337225,
    ("technology", "calvo", "Выпуск"): 0.01249910,
    ("technology", "flex", "Инвестиции"): 0.05470091,
    ("technology", "calvo", "Инвестиции"): 0.04947752,
    ("monetary", "calvo", "Выпуск"): -0.00431472,
    ("monetary", "calvo", "Инвестиции"): -0.02274988,
    ("monetary", "calvo", "Потребление"): 0.00017552,
    ("monetary", "calvo", "Труд"): -0.00643988,
}


def main() -> None:
    for (shock, regime, variable), expected in EXPECTED.items():
        path = ROOT / "results" / f"otkliki_{shock}_{regime}.csv"
        with path.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        if len(rows) != 41 or [int(x["Период"]) for x in rows] != list(range(41)):
            raise AssertionError(f"Неверное число периодов в {path}")
        actual = float(rows[0][variable])
        if abs(actual - expected) > 6e-8:
            raise AssertionError(f"Число в статье не совпадает с {path}: {variable}")
    for variable in ("Выпуск", "Потребление", "Инвестиции", "Труд"):
        path = ROOT / "results" / "otkliki_monetary_flex.csv"
        with path.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        if any(abs(float(r[variable])) > 1e-9 for r in rows):
            raise AssertionError(f"Нарушена денежная нейтральность: {variable}")
    print("Проверка таблиц статьи и денежной нейтральности выполнена.")


if __name__ == "__main__":
    main()
