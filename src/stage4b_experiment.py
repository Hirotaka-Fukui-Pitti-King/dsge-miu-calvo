"""Воспроизводимый численный эксперимент проверки микрооснования первого порядка."""
from __future__ import annotations
import json
from pathlib import Path
from dataclasses import asdict
from src.model import Parameters
from src.firm_specific_capital import irf
from src.firm_micro_linear import check_micro_equilibrium
from src.firm_specific_steady import solve_symmetric_steady


def run(root: Path | None = None):
    p=Parameters()
    root=root or Path(__file__).resolve().parent.parent
    steady=solve_symmetric_steady(p)
    coefficients,checks=check_micro_equilibrium(p,4.,200)
    impacts={}
    for capital in ('common','specific'):
        impacts[capital]={}
        for shock in ('technology','monetary'):
            record=irf(p,'calvo',capital,shock,4.,200)[0]
            impacts[capital][shock]={key:float(record[key])
                                     for key in ('output','consumption','investment',
                                                 'employment','inflation','capital')}
    result={
        'scope': 'symmetric_nonlinear_steady_plus_first_order_stochastic_micro',
        'nonlinear_transition_equilibrium_solved': False,
        'first_order_aggregate_solution_checked': True,
        'common_adjustment': 4.,
        'steady': asdict(steady),
        'coefficients': asdict(coefficients),
        'micro_checks': checks,
        'impact_irfs': impacts,
        'note': 'Distribution covariance uses first-order firm policies; no second-order GE.'
    }
    output=root/'results'/'stage4b_first_order_micro.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    if steady.maximum_residual>1e-10:
        raise RuntimeError('Нелинейный стационар не удовлетворяет исходным условиям.')
    if max(c['reset_price_foc'] for c in checks.values())>1e-10:
        raise RuntimeError('Ошибка Calvo FOC.')
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return result


if __name__=='__main__':
    run()
