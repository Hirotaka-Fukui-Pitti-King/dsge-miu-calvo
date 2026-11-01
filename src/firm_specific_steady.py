"""Независимое численное симметричное стационарное равновесие отдельных фирм.

Не является решением нелинейного перехода после шока.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.optimize import root


@dataclass(frozen=True)
class SymmetricSteadyState:
    consumption: float
    hours: float
    firm_capital: float
    output: float
    wage: float
    investment: float
    dividends: float
    firm_value: float
    shadow_capital: float
    maximum_residual: float


def solve_symmetric_steady(p):
    """Численный корень исходных нелинейных условий без аналитического steady_state()."""
    beta,alpha,delta,eps=p.beta,p.alpha,p.delta,p.epsilon
    markup_mc=(eps-1)/eps
    rental=1/beta-1+delta

    def residual(logs):
        c,n,k,y,w=np.exp(logs)
        return np.array([
            np.log(y/(k**alpha*n**(1-alpha))),
            np.log(y/(c+delta*k)),
            np.log(w/(p.chi_n*n**p.varphi*c**p.sigma)),
            np.log(w*n/((1-alpha)*markup_mc*y)),
            np.log(alpha*markup_mc*y/(k*rental))
        ])

    solution=root(residual,np.log([1.,.6,5.,1.4,1.]),tol=1e-12)
    err=float(np.max(np.abs(residual(solution.x))))
    if not solution.success and err>1e-11:
        raise RuntimeError("Нет сходимости симметричного стационарного равновесия.")
    c,n,k,y,w=np.exp(solution.x)
    invest=delta*k
    dividends=y-w*n-invest
    value=dividends/(1-beta)
    dprice=(1-eps)*y+eps*w*n/(1-alpha)
    dinvest=-1+beta*rental/(1-beta*(1-delta))
    envelope=rental+(1-delta)
    checks=[err,abs(dprice/y),abs(dinvest),abs(envelope-1/beta),
            abs(y-c-invest),abs(y-k**alpha*n**(1-alpha))]
    return SymmetricSteadyState(float(c),float(n),float(k),float(y),float(w),
                                float(invest),float(dividends),float(value),
                                float(1/beta),float(np.max(checks)))
