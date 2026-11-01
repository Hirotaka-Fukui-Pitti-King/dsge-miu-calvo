"""Аналитические составляющие второго этапа; НЕ полноценный решатель второго порядка."""
from dataclasses import dataclass
import numpy as np
from scipy.special import roots_hermitenorm
from src.model import Parameters, transition_matrix, stable_solution

@dataclass(frozen=True)
class Volatility:
    """Иллюстративные стандартные отклонения независимых инноваций."""
    technology: float = 0.01
    monetary: float = 0.0025
    def covariance(self):
        if min(self.technology, self.monetary) < 0:
            raise ValueError("Стандартные отклонения неотрицательны.")
        return np.diag([self.technology**2, self.monetary**2])

def reset_price(pi, theta, epsilon):
    """Относительная цена, совместимая с точным индексом цен Кальво."""
    if not (0 < theta < 1 and epsilon > 1):
        raise ValueError("Недопустимые параметры Кальво.")
    z = (1-theta*np.exp((epsilon-1)*pi))/(1-theta)
    if z <= 0:
        raise ValueError("Положительная цена пересмотра не существует.")
    return z**(1/(1-epsilon))

def dispersion(pi, old, theta, epsilon):
    p=reset_price(pi,theta,epsilon)
    return (1-theta)*p**(-epsilon)+theta*np.exp(epsilon*pi)*old

def dispersion_curvature(theta,epsilon):
    """Производная d²Δ/dπ² около нулевой инфляции и Δ прошлого периода = 1."""
    if not (0<theta<1 and epsilon>1):
        raise ValueError("Недопустимые параметры Кальво.")
    return epsilon*theta/(1-theta)

def firm_labor(y,k,a,alpha):
    return (y/(a*k**alpha))**(1/(1-alpha))

def firm_marginal_cost(y,k,a,w,alpha):
    return w*firm_labor(y,k,a,alpha)/((1-alpha)*y)

def firm_capital_shadow(y,k,a,w,alpha):
    """Экономия труда от единицы дополнительного уже установленного капитала."""
    return alpha*w*firm_labor(y,k,a,alpha)/((1-alpha)*k)

def investment_cost(inv,k,delta,phi):
    return phi*k*(inv/k-delta)**2/2

def investment_cost_i(inv,k,delta,phi):
    return phi*(inv/k-delta)

def investment_cost_k(inv,k,delta,phi):
    return phi*(delta**2-(inv/k)**2)/2

def shock_exposures(p, regime):
    """Линейные экспозиции к инновациям; не полная политика второго порядка."""
    _,h,_=stable_solution(transition_matrix(p,regime))
    c=h[0,1:3]
    if regime=="calvo":
        n=h[2,1:3]
    else:
        n=(np.array([1.,0.])-p.sigma*c)/(p.varphi+p.alpha)
    rent=p.sigma*c+(1+p.varphi)*n
    return c,rent

def leading_covariance_component(p,regime,volatility=Volatility()):
    """Ведущая часть -Cov(SDF,R)/E[SDF], НЕ равновесная премия."""
    c,r=shock_exposures(p,regime)
    return float(p.sigma*p.steady_ratios()["rk"]*c@volatility.covariance()@r)

def gaussian_diagnostic(p,regime,volatility=Volatility(),order=16):
    """Независимая квадратура по линейной политике и её ошибка Euler."""
    c,r=shock_exposures(p,regime)
    nodes,weights=roots_hermitenorm(order)
    weights=weights/np.sqrt(2*np.pi)
    v=np.array([volatility.technology,volatility.monetary])
    eps=np.stack(np.meshgrid(nodes,nodes,indexing="ij"),axis=-1)
    m=p.beta*np.exp(-p.sigma*np.sum(eps*c*v,axis=-1))
    gross=1-p.delta+p.steady_ratios()["rk"]*np.exp(np.sum(eps*r*v,axis=-1))
    q=weights[:,None]*weights[None,:]
    em=float(np.sum(q*m))
    er=float(np.sum(q*gross))
    emr=float(np.sum(q*m*gross))
    return {"leading_covariance":leading_covariance_component(p,regime,volatility),
            "quadrature_covariance":-(emr-em*er)/em,
            "euler_residual":emr-1}
