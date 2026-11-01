"""Независимая проверка нелинейных уравнений, производных и QZ-решений."""

import unittest

import numpy as np

from src.audit import (audit_impulses, calvo_price_derivative,
                       independent_transition, nonlinear_residual,
                       numerical_jacobian, schur_solution, stationary_residuals)
from src.experiment import impulses
from src.model import Parameters, stable_solution, transition_matrix


class IndependentAuditTests(unittest.TestCase):
    """Проверять экономические ограничения, а не заранее сохранённые корни."""

    def setUp(self):
        self.p = Parameters()

    def test_all_steady_state_residuals(self):
        residuals = stationary_residuals(self.p)
        self.assertGreaterEqual(len(residuals), 15)
        self.assertLess(max(map(abs, residuals.values())), 1e-10)

    def test_steady_state_regimes_are_identical(self):
        self.assertEqual(self.p.steady_state(), Parameters(theta=0).steady_state())

    def test_calvo_recursions_generate_phillips_coefficient(self):
        slope = calvo_price_derivative(self.p)["kappa_from_recursions"]
        self.assertAlmostEqual(slope, (1-self.p.theta)*(1-self.p.beta*self.p.theta)/self.p.theta)
        self.assertAlmostEqual(slope, 0.08583333333333333)

    def test_jacobians_from_nonlinear_conditions(self):
        for regime in ("flex", "calvo"):
            with self.subTest(regime=regime):
                independent, details = independent_transition(self.p, regime)
                np.testing.assert_allclose(independent, transition_matrix(self.p, regime), atol=2e-8, rtol=0)
                self.assertLess(details["difference"], 2e-8)

    def test_jacobian_stepsize_stability(self):
        for regime in ("flex", "calvo"):
            dim = 5 if regime == "flex" else 6
            zero = np.zeros(dim)
            func = lambda zz: nonlinear_residual(zz, zero, self.p, regime)
            d1 = numerical_jacobian(func, zero, step=1e-4)
            d2 = numerical_jacobian(func, zero, step=1e-5)
            self.assertLess(abs(d1-d2).max(), 1e-7)

    def test_ordered_qz_agrees_with_eigenvectors(self):
        for regime in ("flex", "calvo"):
            matrix = independent_transition(self.p, regime)[0]
            eig, policy, law, info = schur_solution(matrix)
            old_eig, old_policy, old_law = stable_solution(transition_matrix(self.p, regime))
            with self.subTest(regime=regime):
                np.testing.assert_allclose(eig, old_eig, atol=2e-8)
                np.testing.assert_allclose(policy, old_policy, atol=2e-8)
                np.testing.assert_allclose(law, old_law, atol=2e-8)
                self.assertGreater(info["smallest_singular_value"], 0.01)
                self.assertLess(info["max_invariance_residual"], 1e-10)

    def test_irfs_agree_between_independent_solvers(self):
        for regime in ("flex", "calvo"):
            for shock in ("technology", "monetary"):
                with self.subTest(regime=regime, shock=shock):
                    new, residual = audit_impulses(self.p, regime, shock, 40)
                    old = impulses(self.p, regime, shock, 40)
                    self.assertLess(residual, 1e-10)
                    self.assertEqual(len(new), 41)
                    for row, row_old in zip(new, old):
                        for field in row_old:
                            self.assertAlmostEqual(row[field], row_old[field], delta=1e-8)

    def test_linear_equilibrium_each_period(self):
        for regime in ("flex", "calvo"):
            matrix, info = independent_transition(self.p, regime)
            _, h, t, _ = schur_solution(matrix)
            for state in (np.array([0.0, 0.01, 0.0]), np.array([0.0, 0.0, 0.0025])):
                for _ in range(40):
                    z = np.r_[state, h @ state]
                    expected = np.r_[t @ state, h @ t @ state]
                    d = 5 if regime == "flex" else 6
                    zeros = np.zeros(d)
                    j0 = numerical_jacobian(lambda x: nonlinear_residual(x, zeros, self.p, regime), zeros)
                    j1 = numerical_jacobian(lambda x: nonlinear_residual(zeros, x, self.p, regime), zeros)
                    self.assertLess(np.max(abs(j0@z+j1@expected)), 1e-10)
                    state = t @ state

    def test_linear_approximation_has_quadratic_error(self):
        for regime in ("flex", "calvo"):
            matrix = independent_transition(self.p, regime)[0]
            _, h, t, _ = schur_solution(matrix)
            state = np.array([0., 0.01, 0.0025])
            z = np.r_[state, h @ state]
            expected = np.r_[t @ state, h @ t @ state]
            err = lambda scale: float(np.max(abs(nonlinear_residual(scale*z, scale*expected, self.p, regime))))
            # Квадратическая ошибка исходных нелинейных FOC при линейном решении.
            self.assertGreater(err(1.0), 1e-10)
            self.assertLess(err(0.5)/err(1.0), 0.26)
            self.assertGreater(err(0.5)/err(1.0), 0.24)

    def test_monetary_neutrality_and_nonneutrality(self):
        flex, _ = audit_impulses(self.p, "flex", "monetary")
        calvo, _ = audit_impulses(self.p, "calvo", "monetary")
        for row in flex:
            for field in ("Выпуск", "Потребление", "Инвестиции", "Труд", "Капитал"):
                self.assertLess(abs(row[field]), 1e-9)
        self.assertGreater(abs(calvo[0]["Выпуск"]), 1e-4)

    def test_convergence_after_transitory_shocks(self):
        for regime in ("flex", "calvo"):
            for shock in ("technology", "monetary"):
                rows, _ = audit_impulses(self.p, regime, shock, 500)
                self.assertLess(max(abs(v) for k, v in rows[-1].items() if k != "Период"), 1e-8)

    def test_money_demand_interest_rate_convention(self):
        s, p = self.p.steady_state(), self.p
        def money(c, log_gross):
            consumption = s["c"] * np.exp(c)
            gross = (1+s["i_nom"]) * np.exp(log_gross)
            return (p.chi_m * consumption**p.sigma * gross/(gross-1))**(1/p.eta_m)
        step = 1e-6
        consumption_derivative = (np.log(money(step, 0)) - np.log(money(-step, 0)))/(2*step)
        interest_derivative = (np.log(money(0, step)) - np.log(money(0, -step)))/(2*step)
        self.assertAlmostEqual(consumption_derivative, p.sigma/p.eta_m, delta=1e-7)
        self.assertAlmostEqual(interest_derivative, -1/(s["i_nom"]*p.eta_m), delta=1e-6)


if __name__ == "__main__":
    unittest.main()
