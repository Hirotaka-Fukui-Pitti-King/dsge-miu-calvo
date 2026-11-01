"""Сопоставимые отклики четырёх экономик и проверяемые файлы результатов."""
from __future__ import annotations
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from src.model import Parameters
from src.firm_specific_capital import solve,irf,woodford_coefficients

VARIABLES={
 'output':('Output',r'$\hat{y}_t$'),
 'consumption':('Consumption',r'$\hat{c}_t$'),
 'investment':('Investment',r'$\hat{I}_t$'),
 'employment':('Employment',r'$\hat{n}_t$'),
 'capital':('Capital stock',r'$\hat{k}_t$'),
 'inflation':('Inflation',r'$\pi_t$'),
 'nominal_rate':('Nominal interest rate',r'$\tilde{i}_t$'),
 'real_marginal_cost':('Real marginal cost',r'$\widehat{mc}_t$'),
 'marginal_q':('Marginal Tobin q',r'$\tilde{q}_t$'),
}
# Здесь "common" означает тот же параметр регулирования капитала,
# а не прежний эталон без издержек.
REGIMES=[('common','flex','Common / flexible'),('common','calvo','Common / Calvo'),
         ('specific','flex','Firm-specific / flexible'),('specific','calvo','Firm-specific / Calvo')]

def run(root:Path,adjustment:float=4.,p:Parameters|None=None):
    p=p or Parameters()
    result=root/'results'/'stage3'
    figs=root/'paper'/'figures'/'stage3'
    result.mkdir(parents=True,exist_ok=True);figs.mkdir(parents=True,exist_ok=True)
    checks={}
    for cap,regime,label in REGIMES:
        eq=solve(p,regime,cap,adjustment)
        checks[cap+'_'+regime]={
            'eigenvalues':[[float(np.real(e)),float(np.imag(e))] for e in eq['eigenvalues']],
            'bk_invariance_residual':eq['bk_residual']}
    c=woodford_coefficients(p,adjustment)
    checks['woodford_relative_capital']={
        'persistence':c.persistence,'investment_price':c.investment_price,
        'reset_capital':c.reset_capital,'relative_roots':c.relative_roots,
        'phillips_slope':c.phillips_slope,'polynomial_residual':c.polynomial_residual,
        'investment_residual':c.investment_residual,'reset_residual':c.reset_residual}
    checks['common_phillips_slope']=(1-p.theta)*(1-p.beta*p.theta)/p.theta
    checks['adjustment_cost']=adjustment
    with (result/'checks.json').open('w',encoding='utf-8') as stream:json.dump(checks,stream,indent=2,ensure_ascii=False)
    for shock in ('technology','monetary'):
        records={}
        for cap,regime,label in REGIMES:
            rows=irf(p,regime,cap,shock,adjustment)
            records[(cap,regime)]=rows
            with (result/f'{shock}_{cap}_{regime}.csv').open('w',newline='',encoding='utf-8') as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        for name,(display,symbol) in VARIABLES.items():
            fig,ax=plt.subplots(figsize=(7.4,4.5))
            for cap,regime,label in REGIMES:
                rows=records[(cap,regime)]
                ax.plot([r['period'] for r in rows],[100*r[name] for r in rows],
                        label=label,linewidth=1.7,linestyle='--' if cap=='specific' else '-')
            ax.axhline(0,color='gray',linewidth=.7)
            ax.set_xlabel('Quarters after shock')
            ax.set_ylabel(f'{symbol}: log deviation × 100')
            ax.set_title(display+' — '+('technology shock' if shock=='technology' else 'monetary-policy shock'))
            ax.legend(fontsize=8,loc='best');ax.grid(alpha=.2)
            fig.tight_layout();fig.savefig(figs/f'{shock}_{name}.svg',format='svg');plt.close(fig)
    return checks

if __name__=='__main__':
    r=run(Path(__file__).resolve().parent.parent)
    print('Условное сравнительное решение первого порядка записано в results/stage3.')
    print('Наклон Филлипса (общий / отдельный капитал):',r['common_phillips_slope'],r['woodford_relative_capital']['phillips_slope'])
