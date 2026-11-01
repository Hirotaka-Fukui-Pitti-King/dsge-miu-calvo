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




def check_second_order() -> None:
    """Проверить численные заявления о решении общего капитала второго порядка."""
    import json
    data=json.loads((ROOT/'results'/'stage2_common_second_order.json').read_text(encoding='utf-8'))
    assert abs(data['shock_standard_deviations']['technology']-0.001)<1e-14
    assert abs(data['shock_standard_deviations']['monetary']-0.00025)<1e-14
    a=data['flex'];b=data['calvo']
    assert abs(a['stochastic_equilibrium']['risk_premium']-1.5516931295422864e-8)<1e-10
    assert abs(b['stochastic_equilibrium']['risk_premium']-1.2715258845830135e-8)<1e-10
    assert b['stochastic_equilibrium']['max_equilibrium_residual']<1e-8
    assert abs(b['stochastic_equilibrium']['asset_pricing_residual'])<1e-10
    assert abs(data['cev_calvo_relative_flex']['conditional']+0.0013944882015276372)<1e-5
    assert abs(data['cev_calvo_relative_flex']['unconditional']+0.001631736538083453)<1e-5
    qmd=(ROOT/'paper'/'article.qmd').read_text(encoding='utf-8')
    for required in ('-0.13945%', '-0.16317%', 'Second-order stochastic allocation'):
        assert required in qmd, required

if __name__ == "__main__":
    main()
    check_second_order()
