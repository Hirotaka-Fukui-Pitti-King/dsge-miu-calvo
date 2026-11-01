"""Тесты аналитического стационара и равновесной динамики."""

import unittest
import numpy as np

from src.model import Parameters, transition_matrix, stable_solution
from src.experiment import impulses


class ModelTests(unittest.TestCase):
    """Автоматическая проверка основных экономических тождеств."""

    def setUp(self) -> None:
        self.p = Parameters()
        self.s = self.p.steady_state()

    def test_stationary_resource_constraint(self) -> None:
        self.assertAlmostEqual(self.s["y"], self.s["c"] + self.s["investment"])
        self.assertAlmostEqual(self.s["investment"], self.p.delta * self.s["k"])

    def test_stationary_factors(self) -> None:
        p, s = self.p, self.s
        self.assertAlmostEqual(s["rk"], s["mc"] * p.alpha * s["y"] / s["k"])
        self.assertAlmostEqual(s["w"], s["mc"] * (1-p.alpha) * s["y"] / s["n"])
        self.assertAlmostEqual(s["y"], s["k"]**p.alpha * s["n"]**(1-p.alpha))
        self.assertAlmostEqual(p.chi_n * s["n"]**p.varphi,
                               s["c"]**(-p.sigma) * s["w"])

    def test_stationary_euler_and_money(self) -> None:
        p, s = self.p, self.s
        self.assertAlmostEqual(1, p.beta * (s["rk"] + 1 - p.delta))
        self.assertAlmostEqual(1, p.beta * (1 + s["i_nom"]))
        self.assertAlmostEqual(p.chi_m * s["m"]**(-p.eta_m),
                               s["c"]**(-p.sigma) * s["i_nom"]/(1+s["i_nom"]))

    def test_bk_calvo(self) -> None:
        a = transition_matrix(self.p, "calvo")
        eig, policy, law = stable_solution(a)
        self.assertEqual(sum(abs(eig) > 1), 3)
        self.assertEqual(policy.shape, (3, 3))
        self.assertLess(max(abs(np.linalg.eigvals(law))), 1)
        np.testing.assert_allclose(np.sort(eig.real),
                                   [0.8, 0.9, 0.945482, 1.06838109, 1.6639033, 2.24357835],
                                   atol=2e-6)

    def test_bk_flexible(self) -> None:
        a = transition_matrix(self.p, "flex")
        eig, policy, law = stable_solution(a)
        self.assertEqual(sum(abs(eig) > 1), 2)
        self.assertEqual(policy.shape, (2, 3))
        self.assertLess(max(abs(np.linalg.eigvals(law))), 1)

    def test_monetary_neutrality_flexible(self) -> None:
        rows = impulses(self.p, "flex", "monetary", 20)
        for row in rows:
            for variable in ("Выпуск", "Потребление", "Инвестиции", "Труд", "Капитал"):
                self.assertAlmostEqual(row[variable], 0, places=10)

    def test_calvo_is_not_money_neutral(self) -> None:
        rows = impulses(self.p, "calvo", "monetary", 5)
        self.assertGreater(abs(rows[0]["Выпуск"]), 1e-8)


if __name__ == "__main__":
    unittest.main()
