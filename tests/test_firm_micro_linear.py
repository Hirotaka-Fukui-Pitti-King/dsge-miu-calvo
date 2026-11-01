"""Регрессия первого порядка и независимая проверка микроусловий Кальво."""
import unittest
import numpy as np
from src.model import Parameters
from src.firm_micro_linear import (
    micro_coefficients, relative_investment_euler, reset_price_foc,
    distribution_moments, check_micro_equilibrium)
from src.firm_specific_capital import woodford_coefficients, irf, _capital_euler, _q, _current


class MicroEquilibriumTest(unittest.TestCase):
    def setUp(self):
        self.p=Parameters()
        self.coeff=micro_coefficients(self.p,4.)

    def test_micro_coefficients_independent_woodford(self):
        original=woodford_coefficients(self.p,4.)
        self.assertLess(self.coeff.micro_equation_residual,1e-11)
        self.assertAlmostEqual(self.coeff.capital_persistence,original.persistence,delta=1e-10)
        self.assertAlmostEqual(self.coeff.investment_price,original.investment_price,delta=1e-10)
        self.assertAlmostEqual(self.coeff.reset_capital,original.reset_capital,delta=1e-10)
        self.assertAlmostEqual(self.coeff.nkpc_slope,original.phillips_slope,delta=1e-11)

    def test_relative_firm_euler(self):
        for capital in (-.1,0.,.02):
            for price in (-.03,0.,.04):
                self.assertLess(abs(relative_investment_euler(
                    self.p,self.coeff,capital,price,4.)),1e-11)

    def test_price_foc_and_distribution_moments(self):
        coeff,checks=check_micro_equilibrium(self.p,4.,200)
        for shock in ('monetary','technology'):
            self.assertLess(checks[shock]['reset_price_foc'],1e-10)
            self.assertLess(checks[shock]['relative_investment_euler'],1e-10)
            self.assertLess(checks[shock]['first_order_ces'],1e-12)
            self.assertLess(checks[shock]['mean_relative_capital'],1e-12)
        self.assertAlmostEqual(checks['monetary']['impact_output'],-.00845635171846647,delta=1e-9)
        self.assertAlmostEqual(checks['technology']['impact_output'],.007740630540763396,delta=1e-9)

    def test_capital_envelope_adjustment_derivative(self):
        p=self.p
        cost=4.
        s=p.steady_ratios()
        k,a,c,n=0.,0.,0.,0.
        y,mc,i=_current(k,a,c,n,p)
        q=_q(k,i,p,cost)
        k1=(1-p.delta)*k+p.delta*i
        # При q_new != 0 полное условие содержит beta*q_new;
        # старое beta*(1-delta)*q_new ошибочно.
        c1=.0005
        n1=.001
        actual=_capital_euler(k1,0.,c,c1,n1,q,p,cost)
        yn,_,inext=_current(k1,0.,c1,n1,p)
        qnext=_q(k1,inext,p,cost)
        rho1=p.sigma*c1+(1+p.varphi)*n1-k1
        expected=q+p.sigma*(c1-c)-s['q']*rho1-p.beta*qnext
        self.assertAlmostEqual(actual,expected,delta=1e-12)
        self.assertGreater(abs(p.beta*p.delta*qnext),1e-8)


if __name__=='__main__':
    unittest.main()
