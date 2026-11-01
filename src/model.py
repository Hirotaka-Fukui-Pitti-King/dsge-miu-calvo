"""Расчёт стационарного состояния и линейной системы общего равновесия."""

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Parameters:
    """Параметры предпочтений, технологии, цен и денежной политики."""

    beta: float = 0.99
    alpha: float = 0.33
    delta: float = 0.025
    epsilon: float = 6.0
    theta: float = 0.75
    sigma: float = 1.0
    varphi: float = 1.0
    chi_n: float = 1.0
    chi_m: float = 1.0
    eta_m: float = 1.0
    phi_pi: float = 1.5
    phi_y: float = 0.125
    rho_a: float = 0.9
    rho_v: float = 0.8

    def validate(self) -> None:
        """Проверка допустимости выбранных параметров."""
        if not 0 < self.beta < 1:
            raise ValueError("Требуется 0 < beta < 1.")
        if not 0 < self.alpha < 1:
            raise ValueError("Требуется 0 < alpha < 1.")
        if not 0 < self.delta < 1:
            raise ValueError("Требуется 0 < delta < 1.")
        if not self.epsilon > 1:
            raise ValueError("Требуется epsilon > 1.")
        if not 0 <= self.theta < 1:
            raise ValueError("Требуется 0 <= theta < 1.")
        if not (self.sigma > 0 and self.varphi > 0 and self.chi_n > 0):
            raise ValueError("Параметры потребления и труда должны быть положительны.")
        if not (self.chi_m > 0 and self.eta_m > 0):
            raise ValueError("Параметры полезности денег должны быть положительны.")
        if not (abs(self.rho_a) < 1 and abs(self.rho_v) < 1):
            raise ValueError("Экзогенные процессы должны быть стационарны.")
        if not 0 < self.steady_ratios()["s_i"] < 1:
            raise ValueError("Требуется 0 < I/Y < 1.")

    def steady_ratios(self) -> dict[str, float]:
        """Соотношения, не зависящие от уровня труда."""
        mc = (self.epsilon - 1) / self.epsilon
        rk = 1 / self.beta - 1 + self.delta
        k_y = self.alpha * mc / rk
        s_i = self.delta * k_y
        return {"mc": mc, "rk": rk, "i_nom": 1 / self.beta - 1,
                "k_y": k_y, "s_i": s_i, "s_c": 1 - s_i,
                "q": self.beta * rk}

    def steady_state(self) -> dict[str, float]:
        """Аналитическое стационарное состояние при нулевой инфляции."""
        self.validate()
        ratios = self.steady_ratios()
        k_n = (self.alpha * ratios["mc"] / ratios["rk"]) ** (1 / (1 - self.alpha))
        y_n = k_n ** self.alpha
        wage = ratios["mc"] * (1 - self.alpha) * y_n
        consumption_n = ratios["s_c"] * y_n
        labor = (wage * consumption_n ** (-self.sigma) / self.chi_n) ** (1 / (self.varphi + self.sigma))
        output = y_n * labor
        consumption = ratios["s_c"] * output
        capital = k_n * labor
        investment = self.delta * capital
        money = (self.chi_m * consumption ** self.sigma *
                 (1 + ratios["i_nom"]) / ratios["i_nom"]) ** (1 / self.eta_m)
        return {**ratios, "k_n": k_n, "y_n": y_n, "w": wage, "n": labor,
                "y": output, "c": consumption, "k": capital,
                "investment": investment, "m": money}


def _calvo_map(z: np.ndarray, p: Parameters) -> np.ndarray:
    """Отображение E_t z_{t+1} = A z_t для модели с негибкими ценами.

    Порядок переменных: капитал, технология, денежный шок,
    потребление, инфляция, труд.
    """
    k, a, v, c, pi, n = z
    s = p.steady_ratios()
    kappa = (1 - p.theta) * (1 - p.beta * p.theta) / p.theta
    y = a + p.alpha * k + (1 - p.alpha) * n
    mc = p.sigma * c + (p.varphi + p.alpha) * n - a - p.alpha * k
    k_next = (1 - p.delta) * k + p.delta / s["s_i"] * (y - s["s_c"] * c)
    e_pi = (pi - kappa * mc) / p.beta
    e_c = c + (p.phi_pi * pi + p.phi_y * y + v - e_pi) / p.sigma
    e_n = (k_next + p.sigma / s["q"] * (e_c - c) - p.sigma * e_c) / (1 + p.varphi)
    return np.array([k_next, p.rho_a * a, p.rho_v * v, e_c, e_pi, e_n])


def _flexible_map(z: np.ndarray, p: Parameters) -> np.ndarray:
    """Отображение E_t z_{t+1} = A z_t для модели с гибкими ценами.

    Порядок переменных: капитал, технология, денежный шок,
    потребление, инфляция. Труд определён условием mc_hat = 0.
    """
    k, a, v, c, pi = z
    s = p.steady_ratios()
    d = p.varphi + p.alpha
    n = (a + p.alpha * k - p.sigma * c) / d
    y = a + p.alpha * k + (1 - p.alpha) * n
    k_next = (1 - p.delta) * k + p.delta / s["s_i"] * (y - s["s_c"] * c)
    a_next = p.rho_a * a
    # В будущей арендной ставке капитал предопределён, а труд зависит от c_{t+1}.
    const_rk = ((1 + p.varphi) * (a_next + p.alpha * k_next) / d) - k_next
    coefficient_c = p.sigma * (1 - (1 + p.varphi) / d)
    e_c = (c + s["q"] / p.sigma * const_rk) / (1 - s["q"] / p.sigma * coefficient_c)
    e_pi = p.phi_pi * pi + p.phi_y * y + v - p.sigma * (e_c - c)
    return np.array([k_next, a_next, p.rho_v * v, e_c, e_pi])


def transition_matrix(p: Parameters, regime: str) -> np.ndarray:
    """Матрица коэффициентов линеаризованной системы."""
    p.validate()
    if regime == "calvo":
        if p.theta == 0:
            raise ValueError("Для theta = 0 используйте режим 'flex'.")
        fn, dimension = _calvo_map, 6
    elif regime == "flex":
        fn, dimension = _flexible_map, 5
    else:
        raise ValueError("Неизвестный режим ценообразования.")
    return np.column_stack([fn(np.eye(dimension)[j], p) for j in range(dimension)])


def stable_solution(matrix: np.ndarray, state_count: int = 3,
                    tolerance: float = 1e-7) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Решение на устойчивом подпространстве при выполнении условий БК.

    Возвращает собственные значения, правило для jump variables и
    переходную матрицу состояний. Не подменяет общую QZ-процедуру.
    """
    eigenvalues, eigenvectors = np.linalg.eig(matrix)
    if np.any(np.abs(np.abs(eigenvalues) - 1) < tolerance):
        raise ValueError("Собственное значение слишком близко к единичной окружности.")
    n_jump = matrix.shape[0] - state_count
    if np.count_nonzero(np.abs(eigenvalues) > 1 + tolerance) != n_jump:
        raise ValueError("Нарушено условие числа неустойчивых собственных значений.")
    stable = eigenvectors[:, np.abs(eigenvalues) < 1 - tolerance]
    if stable.shape[1] != state_count:
        raise ValueError("Число устойчивых корней не равно числу состояний.")
    states = stable[:state_count, :]
    if np.linalg.matrix_rank(states, tol=tolerance) != state_count:
        raise ValueError("Не выполнено ранговое условие Бланшара — Кана.")
    solution = stable[state_count:, :] @ np.linalg.inv(states)
    if np.max(np.abs(np.imag(solution))) > tolerance:
        raise ValueError("Получено комплексное правило решения.")
    solution = np.asarray(np.real(solution), dtype=float)
    state_transition = matrix[:state_count, :state_count] + matrix[:state_count, state_count:] @ solution
    if max(abs(np.linalg.eigvals(state_transition))) >= 1 - tolerance:
        raise ValueError("Переходная матрица состояний неустойчива.")
    discrepancy = matrix[state_count:, :state_count] + matrix[state_count:, state_count:] @ solution - solution @ state_transition
    if np.max(np.abs(discrepancy)) > 1e-8:
        raise ValueError("Остаток условия инвариантности ненулевой.")
    return np.sort_complex(eigenvalues), solution, state_transition


def observable_deviations(z: np.ndarray, p: Parameters, regime: str,
                          expected_next: np.ndarray) -> dict[str, float]:
    """Наблюдаемые логарифмические отклонения от стационара."""
    if regime == "calvo":
        k, a, v, c, pi, n = z
        mc = p.sigma * c + (p.varphi + p.alpha) * n - a - p.alpha * k
        e_pi = expected_next[4]
    elif regime == "flex":
        k, a, v, c, pi = z
        n = (a + p.alpha * k - p.sigma * c) / (p.varphi + p.alpha)
        mc = 0.0
        e_pi = expected_next[4]
    else:
        raise ValueError("Неизвестный режим.")
    s = p.steady_ratios()
    y = a + p.alpha * k + (1 - p.alpha) * n
    investment = (y - s["s_c"] * c) / s["s_i"]
    wage = p.sigma * c + p.varphi * n
    rk = p.sigma * c + (1 + p.varphi) * n - k
    nominal_rate = p.phi_pi * pi + p.phi_y * y + v
    money = (p.sigma * c - nominal_rate / s["i_nom"]) / p.eta_m
    return {"Выпуск": y, "Потребление": c, "Инвестиции": investment,
            "Труд": n, "Капитал": k, "Инфляция": pi,
            "Номинальная ставка": nominal_rate,
            "Ожидаемая реальная ставка": nominal_rate - e_pi,
            "Реальные денежные остатки": money,
            "Реальная заработная плата": wage,
            "Арендная ставка капитала": rk,
            "Предельные издержки": mc}
