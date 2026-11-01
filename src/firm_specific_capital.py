"""Линейная экономика с капиталом отдельных фирм и сравнимыми затратами инвестирования.

Коэффициенты относительного капитала и цены получены из уравнений
(24), (29), (30), (36), (38), (41), (44) Woodford (2005).
Для общего рынка труда применяется нулевая эластичность *относительной*
заработной платы по выпуску отдельной фирмы (ν=0). Совокупная ставка
заработной платы по-прежнему эндогенна: w_hat=σ c_hat+φ n_hat.
Это адаптация локальных относительных уравнений, НЕ дословная экономика
Woodford с отраслевыми рынками труда.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from numpy.polynomial import Polynomial as Poly
from scipy.linalg import ordqz
from src.model import Parameters


@dataclass(frozen=True)
class SpecificCoefficients:
    persistence: float
    investment_price: float
    reset_capital: float
    price_denominator: float
    phillips_slope: float
    relative_roots: tuple[float, float]
    polynomial_residual: float
    investment_residual: float
    reset_residual: float


def woodford_coefficients(p: Parameters, adjustment: float) -> SpecificCoefficients:
    """Устойчивая ветвь квартетного уравнения при общей заработной плате."""
    if p.theta <= 0 or p.theta >= 1 or adjustment <= 0:
        raise ValueError("Нужны 0 < theta < 1 и положительные затраты корректировки.")
    b, h, eps = p.beta, p.theta, p.epsilon
    # Производственная эластичность: не путать с вероятностью Кальво.
    omega = p.alpha / (1 - p.alpha)
    rho_y = omega
    rho_k = omega
    xi_capital = (1 - b * (1 - p.delta)) * rho_y * eps / adjustment
    L = Poly([0.0, 1.0])
    Q = Poly([b, -(1 + b + (1-b*(1-p.delta))*rho_k/adjustment), 1.0])
    V = ((1 + omega*eps)*(1-h*b*L)**2
         - h*h*b*omega*xi_capital*L)*Q(b*L) + b*(1-h)*(1-h*b)*omega*xi_capital*L
    candidates = []
    for x in V.roots():
        if abs(x.imag)>1e-8 or not 0 < x.real < 1:
            continue
        lam=float(x.real)
        tau=h*xi_capital*lam/(1-h*b*lam)
        den=1+omega*eps-omega*tau*h*b/(1-h*b*lam)
        psi=omega*(1-h*b)/((1-h*b*lam)*den)
        rel=np.array([[h+(1-h)*tau*psi,-(1-h)*psi*lam],[-tau,lam]])
        eigen=np.linalg.eigvals(rel)
        if np.max(np.abs(eigen)) >= 1 - 1e-10 or den <= 0 or psi <= 0 or tau <= 0:
            continue
        slope=(1-h)*(1-h*b)/(h*den)
        candidates.append(SpecificCoefficients(lam,tau,psi,den,slope,
            tuple(float(z.real) for z in sorted(eigen,key=lambda x:x.real)),
            float(abs(V(lam))),
            float(abs((1-h*b*lam)*tau - h*xi_capital*lam)),
            float(abs(den*psi - omega*(1-h*b)/(1-h*b*lam)))))
    if len(candidates)!=1:
        raise ValueError("Не найдена единственная устойчивая ветвь капитала и цен.")
    return candidates[0]


def _current(k,a,c,n,p):
    s=p.steady_ratios()
    output=a+p.alpha*k+(1-p.alpha)*n
    mc=p.sigma*c+(p.varphi+p.alpha)*n-a-p.alpha*k
    i_hat=(output-s['s_c']*c)/s['s_i']
    return output,mc,i_hat


def _q(k,i_hat,p,adjustment):
    return adjustment*p.delta*(i_hat-k)


def _capital_euler(k_new,a_new,c_now,c_new,n_new,q_now,p,adjustment):
    s=p.steady_ratios()
    output_new,_,i_new=_current(k_new,a_new,c_new,n_new,p)
    q_new=_q(k_new,i_new,p,adjustment)
    rho_new=p.sigma*c_new+(1+p.varphi)*n_new-k_new
    return q_now+p.sigma*(c_new-c_now)-s['q']*rho_new-p.beta*(1-p.delta)*q_new


def _map_calvo(z,p,adjustment,firm_specific):
    k,a,v,c,pi,n=z
    s=p.steady_ratios()
    output,mc,i_hat=_current(k,a,c,n,p)
    k_new=(1-p.delta)*k+p.delta*i_hat
    a_new=p.rho_a*a
    q=_q(k,i_hat,p,adjustment)
    if firm_specific:
        slope=woodford_coefficients(p,adjustment).phillips_slope
    else:
        slope=(1-p.theta)*(1-p.beta*p.theta)/p.theta
    e_pi=(pi-slope*mc)/p.beta
    i_nom=p.phi_pi*pi+p.phi_y*output+v
    e_c=c+(i_nom-e_pi)/p.sigma
    # Уравнение капитала линейно по ожидаемой занятости.
    f0=_capital_euler(k_new,a_new,c,e_c,0.0,q,p,adjustment)
    f1=_capital_euler(k_new,a_new,c,e_c,1.0,q,p,adjustment)
    e_n=-f0/(f1-f0)
    return np.array([k_new,a_new,p.rho_v*v,e_c,e_pi,e_n])


def _map_flex(z,p,adjustment):
    k,a,v,c,pi=z
    n=(a+p.alpha*k-p.sigma*c)/(p.varphi+p.alpha)
    output,mc,i_hat=_current(k,a,c,n,p)
    k_new=(1-p.delta)*k+p.delta*i_hat
    a_new=p.rho_a*a
    q=_q(k,i_hat,p,adjustment)
    def error(c_new):
        n_new=(a_new+p.alpha*k_new-p.sigma*c_new)/(p.varphi+p.alpha)
        return _capital_euler(k_new,a_new,c,c_new,n_new,q,p,adjustment)
    f0=error(0.0); f1=error(1.0)
    e_c=-f0/(f1-f0)
    i_nom=p.phi_pi*pi+p.phi_y*output+v
    e_pi=i_nom-p.sigma*(e_c-c)
    return np.array([k_new,a_new,p.rho_v*v,e_c,e_pi])


def matrix(p:Parameters,regime:str,capital:str,adjustment:float=4.0):
    """Линейный оператор системы ожиданий при сопоставимых издержках."""
    if adjustment<=0:raise ValueError("Затраты корректировки должны быть положительными.")
    if capital not in ('common','specific') or regime not in ('calvo','flex'):
        raise ValueError("Неизвестная структура капитала либо цен.")
    if regime=='calvo':
        f=lambda z:_map_calvo(z,p,adjustment,capital=='specific')
        n=6
    else:
        f=lambda z:_map_flex(z,p,adjustment)
        n=5
    return np.column_stack([f(np.eye(n)[j]) for j in range(n)])


def solve(p:Parameters,regime:str,capital:str,adjustment:float=4.0):
    A=matrix(p,regime,capital,adjustment)
    ns=3
    # Schur для устойчивого инвариантного подпространства.
    S,T,alpha,beta,Q,Z=ordqz(A,np.eye(len(A)),sort='iuc')
    eig=alpha/beta
    stable=np.abs(eig)<1-1e-8
    if np.count_nonzero(stable)!=ns:
        raise ValueError("Нарушено условие количества корней Бланшара — Кана.")
    Zs=Z[:,:ns]
    if np.linalg.matrix_rank(Zs[:ns])!=ns:
        raise ValueError("Нарушено условие ранга Бланшара — Кана.")
    H=np.real_if_close(Zs[ns:]@np.linalg.inv(Zs[:ns]))
    trans=np.real_if_close(A[:ns,:ns]+A[:ns,ns:]@H)
    residual=A[ns:,:ns]+A[ns:,ns:]@H-H@trans
    if np.max(np.abs(residual))>1e-9:
        raise ValueError("Невязка инвариантности подпространства слишком велика.")
    return {'matrix':A,'eigenvalues':np.sort_complex(eig),'policy':H,
            'transition':trans,'bk_residual':float(np.max(np.abs(residual)))}


def irf(p:Parameters,regime:str,capital:str,shock:str,adjustment:float=4.,horizon:int=40):
    sol=solve(p,regime,capital,adjustment)
    state=np.zeros(3)
    state[1 if shock=='technology' else 2]=.01 if shock=='technology' else .0025
    rows=[]
    for t in range(horizon+1):
        z=np.r_[state,sol['policy']@state]
        k,a,v,c,pi=z[:5]
        n=z[5] if regime=='calvo' else (a+p.alpha*k-p.sigma*c)/(p.varphi+p.alpha)
        y,mc,ii=_current(k,a,c,n,p)
        q=_q(k,ii,p,adjustment)
        nominal=p.phi_pi*pi+p.phi_y*y+v
        rows.append({'period':t,'output':y,'consumption':c,'investment':ii,
                     'employment':n,'capital':k,'inflation':pi,'nominal_rate':nominal,
                     'real_marginal_cost':mc,'marginal_q':q})
        state=sol['transition']@state
    return rows
