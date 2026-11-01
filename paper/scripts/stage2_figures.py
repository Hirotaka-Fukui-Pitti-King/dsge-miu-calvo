"""Англоязычные рисунки для проверенных аналитических диагностик второго порядка."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src.model import Parameters
from src.stage2_foundations import Volatility
import src.stage2_foundations as foundations


def dispersion(pi, old, theta, epsilon):
    """Перенос дисперсии при данном росте цен."""
    fn = getattr(foundations, 'dispersion', None)
    if fn is None:
        fn = foundations.price_dispersion_next
    return fn(pi, old, theta, epsilon)


def dispersion_curvature(theta, epsilon):
    fn = getattr(foundations, 'dispersion_curvature', None)
    if fn is None:
        fn = foundations.price_dispersion_curvature
    return fn(theta, epsilon)


def leading_covariance_component(p, regime, vol):
    fn = getattr(foundations, 'leading_covariance_component', None)
    if fn is None:
        fn = foundations.leading_risk_covariance
    return fn(p, regime, vol)


def main():
    p=Parameters()
    destination=Path(__file__).resolve().parents[1]/'figures'
    destination.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Serif','mathtext.fontset':'dejavuserif','svg.fonttype':'path',
                         'svg.hashsalt':'dsge-stage2','font.size':9.5})
    x=np.linspace(-.003,.003,121)
    y=np.array([dispersion(pi,1,p.theta,p.epsilon)-1 for pi in x])
    quadratic=.5*dispersion_curvature(p.theta,p.epsilon)*x**2
    fig,ax=plt.subplots(figsize=(6.8,3.5))
    ax.plot(100*x,1e4*y,label='Exact price-index recursion',lw=2)
    ax.plot(100*x,1e4*quadratic,'--',label='Second-order expansion',lw=2)
    ax.set(xlabel='Quarterly log inflation (percent)',ylabel='Price dispersion above one (× 10⁴)',
           title='Price dispersion around zero inflation')
    ax.legend(frameon=False);ax.grid(alpha=.2);fig.tight_layout()
    fig.savefig(destination/'stage2_price_dispersion.svg',format='svg',metadata={'Date':None});plt.close(fig)
    multiples=np.linspace(0,2,60)
    fig,ax=plt.subplots(figsize=(6.8,3.5))
    for regime,label in [('flex','Flexible prices'),('calvo','Calvo pricing')]:
        yy=[1e4*leading_covariance_component(p,regime,Volatility(.01*v,.0025*v)) for v in multiples]
        ax.plot(multiples,yy,label=label,lw=2)
    ax.set(xlabel='Innovation standard-deviation multiplier',
           ylabel='Leading covariance component (basis points)',
           title='Covariance diagnostic, not an equilibrium risk premium')
    ax.legend(frameon=False);ax.grid(alpha=.2);fig.tight_layout()
    fig.savefig(destination/'stage2_covariance_diagnostic.svg',format='svg',metadata={'Date':None});plt.close(fig)

if __name__=='__main__':
    main()
