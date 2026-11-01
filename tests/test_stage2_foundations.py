"""Независимые математические проверки частичного этапа 2."""
import unittest
import numpy as np
from src.model import Parameters
from src.stage2_foundations import (
    Volatility, reset_price, dispersion, dispersion_curvature, firm_labor,
    firm_marginal_cost, firm_capital_shadow, investment_cost, investment_cost_i,
    investment_cost_k, leading_covariance_component, gaussian_diagnostic)

class PreliminaryTests(unittest.TestCase):
    def test_price_index_and_curvature(self):
        p=Parameters()
        for pi in (-.001,0,.001):
            r=reset_price(pi,p.theta,p.epsilon)
            self.assertAlmostEqual((1-p.theta)*r**(1-p.epsilon)
                +p.theta*np.exp((p.epsilon-1)*pi),1,places=12)
        h=1e-4
        f=lambda x:dispersion(x,1,p.theta,p.epsilon)
        self.assertAlmostEqual((f(h)+f(-h)-2*f(0))/h**2,
                               dispersion_curvature(p.theta,p.epsilon),delta=3e-4)

    def test_firm_cost_derivatives(self):
        a=.33;y=1.2;k=2.5;w=.8;z=1.1;h=1e-5
        n=firm_labor(y,k,z,a)
        self.assertAlmostEqual(z*k**a*n**(1-a),y)
        self.assertAlmostEqual(firm_marginal_cost(y,k,z,w,a),
            w*(firm_labor(y+h,k,z,a)-firm_labor(y-h,k,z,a))/(2*h),delta=2e-10)
        self.assertAlmostEqual(firm_capital_shadow(y,k,z,w,a),
            -w*(firm_labor(y,k+h,z,a)-firm_labor(y,k-h,z,a))/(2*h),delta=2e-10)

    def test_adjustment_derivatives(self):
        d=.025;k=2.;i=.1;phi=4.;h=1e-5
        f=lambda i,k:investment_cost(i,k,d,phi)
        self.assertAlmostEqual(investment_cost_i(i,k,d,phi),
            (f(i+h,k)-f(i-h,k))/(2*h),places=9)
        self.assertAlmostEqual(investment_cost_k(i,k,d,phi),
            (f(i,k+h)-f(i,k-h))/(2*h),places=9)
        self.assertEqual(f(d*k,k),0)

    def test_covariance_and_euler_error(self):
        p=Parameters()
        for regime in ("flex","calvo"):
            one=leading_covariance_component(p,regime,Volatility(.01,.0025))
            four=leading_covariance_component(p,regime,Volatility(.02,.005))
            self.assertAlmostEqual(four,4*one)
            tiny=gaussian_diagnostic(p,regime,Volatility(.0001,.000025))
            self.assertLess(abs(tiny["leading_covariance"]
                                -tiny["quadrature_covariance"]),1e-10)
            self.assertLess(abs(tiny["euler_residual"]),1e-7)

if __name__=="__main__":
    unittest.main()
