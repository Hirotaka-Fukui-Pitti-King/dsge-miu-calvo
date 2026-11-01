"""Микроэкономические условия оптимальности и моменты линейной меры фирм.

Это строго первое приближение, НЕ нелинейное общее равновесие.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.optimize import root
from src.firm_specific_capital import irf


@dataclass(frozen=True)
class MicroCoefficients:
    capital_persistence: float
    investment_price: float
    reset_capital: float
    nkpc_slope: float
    micro_equation_residual: float


def micro_coefficients(p, adjustment=4.) -> MicroCoefficients:
    """Решить три условия Euler и цены независимо от квартета Woodford."""
    beta, theta, alpha, eps = p.beta, p.theta, p.alpha, p.epsilon
    omega = alpha / (1-alpha)
    rent = p.steady_ratios()['rk'] / (1-alpha)

    def equations(z):
        lam, tau, psi = z
        bx = beta * (adjustment*(lam-1) +
                     adjustment*tau*(1-theta)*psi +
                     rent*eps*(1-theta)*psi-rent)
        by = -beta*theta*(adjustment*tau+rent*eps)
        return np.array([
            adjustment*(lam-1)-lam*bx,
            -adjustment*tau+tau*bx-by,
            psi*((1+omega*eps)*(1-beta*theta*lam) -
                 omega*tau*beta*theta)-omega*(1-beta*theta)
        ])

    solutions = []
    for guess in ((.95,.1,.1),(.7,.05,.2),(.2,.2,.2)):
        trial = root(equations, guess, tol=1e-11)
        lam,tau,psi = trial.x
        if (np.max(np.abs(equations(trial.x)))<1e-10 and
            0<lam<1 and tau>0 and psi>0 and
            not any(np.allclose(trial.x,old) for old in solutions)):
            solutions.append(trial.x)
    if len(solutions)!=1:
        raise ValueError("Не найдена единственная устойчивая политика фирмы.")
    lam,tau,psi = solutions[0]
    denominator = 1+omega*eps-omega*tau*beta*theta/(1-beta*theta*lam)
    kappa=(1-theta)*(1-beta*theta)/(theta*denominator)
    return MicroCoefficients(float(lam),float(tau),float(psi),
                             float(kappa),float(np.max(np.abs(equations(solutions[0])))))


def relative_investment_euler(p, coeff, capital_rel, chosen_price, adjustment=4.):
    """Euler фирмы после выбора цены с ожиданием обеих возможностей Кальво завтра."""
    lam,tau,psi=coeff.capital_persistence,coeff.investment_price,coeff.reset_capital
    next_capital=lam*capital_rel-tau*chosen_price
    expected_next_price=p.theta*chosen_price-(1-p.theta)*psi*next_capital
    q_now=adjustment*(next_capital-capital_rel)
    q_next=adjustment*((lam-1)*next_capital-tau*expected_next_price)
    rent_relative=-(p.epsilon*expected_next_price+next_capital)/(1-p.alpha)
    return float(q_now-p.beta*q_next-p.beta*p.steady_ratios()['rk']*rent_relative)


def reset_price_foc(rows,p,coeff,t,capital_rel=0.):
    """Сумма FOC для когорты, сохраняющей новую номинальную цену."""
    omega=p.alpha/(1-p.alpha)
    price=p.theta/(1-p.theta)*rows[t]['inflation']-coeff.reset_capital*capital_rel
    cap=capital_rel
    total=0.
    survival=1.
    for s in range(t,len(rows)):
        total+=survival*((1+omega*p.epsilon)*price+omega*cap-rows[s]['real_marginal_cost'])
        cap=coeff.capital_persistence*cap-coeff.investment_price*price
        if s+1<len(rows):
            price-=rows[s+1]['inflation']
        survival*=p.beta*p.theta
    return float((1-p.beta*p.theta)*total)


@dataclass
class DistributionMoments:
    """Точные первые и вторые моменты *линейного* стохастического перехода фирм."""
    mean_pre: np.ndarray
    covariance_pre: np.ndarray
    mean_selected_price: np.ndarray
    mean_capital_next: np.ndarray
    covariance_next: np.ndarray
    ces_first_order_residual: np.ndarray


def distribution_moments(rows,p,coeff):
    """Две ветви Кальво; аналитическое перенесение массы и моментов."""
    horizon=len(rows)
    lam,tau,psi=coeff.capital_persistence,coeff.investment_price,coeff.reset_capital
    theta=p.theta
    mean=np.array([0.,-rows[0]['inflation']])
    covariance=np.zeros((2,2))
    means=[];covariances=[];prices=[];capitals=[];crosses=[];ces=[]
    for t in range(horizon):
        inflation=rows[t]['inflation']
        future_inflation=rows[t+1]['inflation'] if t+1<horizon else 0.
        common_reset=theta/(1-theta)*inflation
        keep=np.array([[lam,-tau],[0.,1.]])
        reset=np.array([[lam+tau*psi,0.],[-psi,0.]])
        keep_const=np.array([0.,-future_inflation])
        reset_const=np.array([-tau*common_reset,common_reset-future_inflation])
        mean_keep=keep@mean+keep_const
        mean_reset=reset@mean+reset_const
        next_mean=theta*mean_keep+(1-theta)*mean_reset
        dk=mean_keep-next_mean
        dr=mean_reset-next_mean
        next_cov=theta*(keep@covariance@keep.T+np.outer(dk,dk)) + \
                 (1-theta)*(reset@covariance@reset.T+np.outer(dr,dr))
        selected=theta*mean[1]+(1-theta)*(common_reset-psi*mean[0])
        means.append(mean.copy())
        covariances.append(covariance.copy())
        prices.append(selected)
        capitals.append(next_mean[0])
        crosses.append(next_cov[0,1])
        ces.append((1-p.epsilon)*selected)
        mean=next_mean
        covariance=next_cov
    return DistributionMoments(np.array(means),np.array(covariances),
                               np.array(prices),np.array(capitals),
                               np.array(crosses),np.array(ces))


def check_micro_equilibrium(p,adjustment=4.,horizon=200):
    """Проверить для обоих шоков структуру микро-FОC и индекс цен первого порядка."""
    coefficients=micro_coefficients(p,adjustment)
    checks={}
    for shock in ('technology','monetary'):
        rows=irf(p,'calvo','specific',shock,adjustment,horizon)
        dist=distribution_moments(rows,p,coefficients)
        foc=max(abs(reset_price_foc(rows,p,coefficients,t,capital))
                for t in range(30) for capital in (0.,.03,-.02))
        inv=max(abs(relative_investment_euler(p,coefficients,capital,price,adjustment))
                for capital in (-.1,0.,.02) for price in (-.03,0.,.04))
        checks[shock]={
            'reset_price_foc':float(foc),
            'relative_investment_euler':float(inv),
            'first_order_ces':float(np.max(np.abs(dist.ces_first_order_residual))),
            'mean_relative_capital':float(np.max(np.abs(dist.mean_capital_next))),
            'max_price_capital_covariance_of_linear_policy':float(np.max(np.abs(dist.covariance_next))),
            'impact_output':float(rows[0]['output']),
            'impact_investment':float(rows[0]['investment']),
            'impact_inflation':float(rows[0]['inflation'])
        }
    return coefficients,checks
