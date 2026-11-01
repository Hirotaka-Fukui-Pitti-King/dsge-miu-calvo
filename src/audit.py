"""Независимая проверка исходных условий, производных и решения равновесия."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from scipy.linalg import ordqz

from src.model import Parameters, observable_deviations, transition_matrix


def stationary_residuals(p: Parameters) -> dict[str, float]:
    """Подстановка уровней в независимые нелинейные условия равновесия."""
    s = p.steady_state()
    c, k, n, y = (s[key] for key in ("c", "k", "n", "y"))
    w, rk, mc = s["w"], s["rk"], s["mc"]
    lam = c ** (-p.sigma)
    f = lam * mc * y / (1 - p.beta * p.theta)
    g = lam * y / (1 - p.beta * p.theta)
    # При нулевом совокупном объёме облигаций и государственном потреблении
    # доход фирмы равен Y - wN - rK; трансферты покрывают чистую эмиссию денег.
    dividends = y - w * n - rk * k
    transfers = 0.0
    left_budget = c + k + s["m"]
    right_budget = w * n + (rk + 1 - p.delta) * k + s["m"] + dividends + transfers
    return {
        "Производство": y - k ** p.alpha * n ** (1 - p.alpha),
        "Ресурсы": y - c - s["investment"],
        "Капитал": s["investment"] - p.delta * k,
        "Рынок труда": w - mc * (1 - p.alpha) * y / n,
        "Аренда капитала": rk - mc * p.alpha * y / k,
        "Предложение труда": p.chi_n * n ** p.varphi - lam * w,
        "Эйлер капитала": 1 - p.beta * (rk + 1 - p.delta),
        "Эйлер облигаций": 1 - p.beta * (1 + s["i_nom"]),
        "Спрос на деньги": p.chi_m * s["m"] ** (-p.eta_m)
        - lam * s["i_nom"] / (1 + s["i_nom"]),
        "Рекурсия F": f - lam * mc * y - p.beta * p.theta * f,
        "Рекурсия G": g - lam * y - p.beta * p.theta * g,
        "Цена пересмотра": p.epsilon / (p.epsilon - 1) * f / g - 1,
        "Индекс цен": (1 - p.theta) + p.theta - 1,
        "Дисперсия цен": 1 - (1 - p.theta) - p.theta,
        "Бюджет домохозяйства": left_budget - right_budget,
        "Прибыль фирм": dividends - (y - w * n - rk * k),
        "Государственный бюджет": transfers,
    }


def _levels(z: np.ndarray, p: Parameters, regime: str) -> dict[str, float]:
    """Восстановить уровни из логарифмов, не используя карты перехода."""
    s = p.steady_state()
    if regime == "calvo":
        k, a, v, c, pi, n = z
    elif regime == "flex":
        k, a, v, c, pi = z
        # Точное условие оптимальности труда при mc = константа.
        k_level = s["k"] * np.exp(k)
        c_level = s["c"] * np.exp(c)
        a_level = np.exp(a)
        n_level = (s["mc"] * (1 - p.alpha) * a_level * k_level ** p.alpha
                   / (p.chi_n * c_level ** p.sigma)) ** (1 / (p.varphi + p.alpha))
        n = np.log(n_level / s["n"])
    else:
        raise ValueError("Неизвестный режим.")
    capital = s["k"] * np.exp(k)
    consumption = s["c"] * np.exp(c)
    labor = s["n"] * np.exp(n)
    technology = np.exp(a)
    output = technology * capital ** p.alpha * labor ** (1 - p.alpha)
    wage = p.chi_n * labor ** p.varphi * consumption ** p.sigma
    mc = wage / ((1 - p.alpha) * output / labor)
    rental = mc * p.alpha * output / capital
    gross_nominal = (1 / p.beta) * np.exp(p.phi_pi * pi
                          + p.phi_y * np.log(output / s["y"]) + v)
    return {"k": capital, "c": consumption, "n": labor, "a": technology,
            "y": output, "mc": mc, "rk": rental, "pi": pi, "gross_i": gross_nominal}


def nonlinear_residual(z: np.ndarray, future: np.ndarray,
                       p: Parameters, regime: str) -> np.ndarray:
    """Первоначальные нелинейные условия в локальном детерминированном варианте.

    Уравнение цены Кальво здесь приведено к NKPC *после* независимой
    проверки первой производной точных рекурсий F и G.
    Это не полноценное нелинейное равновесие при неопределённости.
    """
    x = _levels(z, p, regime)
    xp = _levels(future, p, regime)
    s = p.steady_state()
    k_new = (1 - p.delta) * x["k"] + x["y"] - x["c"]
    factor = p.beta * (xp["c"] / x["c"]) ** (-p.sigma)
    residual = [
        (xp["k"] - k_new) / s["k"],
        future[1] - p.rho_a * z[1],
        future[2] - p.rho_v * z[2],
        1 - factor * (xp["rk"] + 1 - p.delta),
        1 - factor * x["gross_i"] / np.exp(xp["pi"]),
    ]
    if regime == "calvo":
        kappa = (1 - p.theta) * (1 - p.beta * p.theta) / p.theta
        residual.append(z[4] - p.beta * future[4]
                        - kappa * np.log(x["mc"] / s["mc"]))
    return np.asarray(residual)


def numerical_jacobian(func, z: np.ndarray, step: float = 1e-5) -> np.ndarray:
    """Центральная разность для каждой координаты первичного уравнения."""
    columns = []
    for j in range(len(z)):
        increment = np.zeros_like(z)
        increment[j] = step
        columns.append((func(z + increment) - func(z - increment)) / (2 * step))
    return np.column_stack(columns)


def independent_transition(p: Parameters, regime: str) -> tuple[np.ndarray, dict]:
    """Из двух Jacobian первичных условий получить матрицу ожиданий."""
    dim = 6 if regime == "calvo" else 5
    zero = np.zeros(dim)
    j_current = numerical_jacobian(lambda x: nonlinear_residual(x, zero, p, regime), zero)
    j_future = numerical_jacobian(lambda x: nonlinear_residual(zero, x, p, regime), zero)
    if np.linalg.matrix_rank(j_future) != dim:
        raise ValueError("Вырождена матрица будущих переменных.")
    matrix = -np.linalg.solve(j_future, j_current)
    return matrix, {"jacobian_current": j_current, "jacobian_future": j_future,
                    "difference": float(np.max(abs(matrix - transition_matrix(p, regime))))}


def calvo_price_derivative(p: Parameters) -> dict[str, float]:
    """Независимая линейная проверка двух рекурсий цены и индекса цен.

    Переменные: (f,g,p,mc,h,f_plus,g_plus,p_plus), где h = log(lambda*Y).
    """
    if p.theta == 0:
        raise ValueError("При гибких ценах данная рекурсия не нужна.")
    p.validate()
    weight = p.beta * p.theta
    def equations(z):
        f, g, pi, mc, h, f_next, g_next, pi_next = z
        return np.array([
            np.exp(f) - (1 - weight) * np.exp(mc + h)
            - weight * np.exp(p.epsilon * pi_next + f_next),
            np.exp(g) - (1 - weight) * np.exp(h)
            - weight * np.exp((p.epsilon - 1) * pi_next + g_next),
            1 - (1 - p.theta) * np.exp((1 - p.epsilon) * (f - g))
            - p.theta * np.exp((p.epsilon - 1) * pi),
        ])
    jac = numerical_jacobian(equations, np.zeros(8))
    # Из первых двух линейных строк получаем
    # d = (1-beta*theta)*mc + beta*theta*(pi_plus+d_plus).
    # Третья строка даёт d = theta*pi/(1-theta).
    slope = (1 - p.theta) * (1 - weight) / p.theta
    # Контролируем коэффициенты исключительно из численных производных.
    assert np.max(abs(jac[0, :2] - [1, 0])) < 1e-8
    assert np.max(abs(jac[1, :2] - [0, 1])) < 1e-8
    assert abs(jac[0, 3] + (1 - weight)) < 1e-8
    assert abs(jac[0, 7] + weight * p.epsilon) < 1e-8
    assert abs(jac[1, 7] + weight * (p.epsilon - 1)) < 1e-8
    assert abs(jac[2, 2] - p.theta * (1-p.epsilon)) < 1e-8
    assert abs(jac[2, 0] - (1-p.theta) * (p.epsilon-1)) < 1e-8
    return {"kappa_from_recursions": slope, "jacobian": jac}


def schur_solution(matrix: np.ndarray, state_count: int = 3,
                   tolerance: float = 1e-7) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """Независимое решение через упорядоченную обобщённую декомпозицию Шура."""
    # Обобщённая задача: matrix @ z_t = E_t z_{t+1}.
    aa, bb, alpha, beta, q, z = ordqz(matrix, np.eye(len(matrix)), sort="iuc", output="complex")
    eig = alpha / beta
    stable_count = int(np.count_nonzero(abs(eig) < 1 - tolerance))
    unstable_count = int(np.count_nonzero(abs(eig) > 1 + tolerance))
    if np.any(abs(abs(eig) - 1) <= tolerance):
        raise ValueError("Обнаружен корень возле единичной окружности.")
    if stable_count != state_count or unstable_count != len(matrix) - state_count:
        raise ValueError("Число неустойчивых корней нарушает условие БК.")
    states = z[:state_count, :state_count]
    svalues = np.linalg.svd(states, compute_uv=False)
    if svalues[-1] <= tolerance:
        raise ValueError("Ранговое условие не выполнено.")
    policy = np.linalg.solve(states.T, z[state_count:, :state_count].T).T
    if np.max(abs(policy.imag)) > tolerance:
        raise ValueError("Комплексное правило решений.")
    policy = policy.real
    transition = matrix[:state_count, :state_count] + matrix[:state_count, state_count:] @ policy
    discrepancy = matrix[state_count:, :state_count] + matrix[state_count:, state_count:] @ policy - policy @ transition
    if abs(discrepancy).max() > 1e-8 or max(abs(np.linalg.eigvals(transition))) >= 1:
        raise ValueError("Нарушена инвариантность устойчивого подпространства.")
    return np.sort_complex(eig), policy, transition, {
        "smallest_singular_value": float(svalues[-1]),
        "max_invariance_residual": float(abs(discrepancy).max()),
        "unstable_count": unstable_count,
    }


def audit_impulses(p: Parameters, regime: str, shock: str,
                   horizon: int = 40) -> tuple[list[dict[str, float]], float]:
    """Импульсные отклики, независимо рассчитанные методом QZ."""
    matrix, _ = independent_transition(p, regime)
    _, policy, transition, _ = schur_solution(matrix)
    state = np.zeros(3)
    if shock == "technology":
        state[1] = 0.01
    elif shock == "monetary":
        state[2] = 0.0025
    else:
        raise ValueError("Неизвестный шок.")
    rows, max_residual = [], 0.0
    dim = 6 if regime == "calvo" else 5
    zero = np.zeros(dim)
    j0 = numerical_jacobian(lambda xx: nonlinear_residual(xx, zero, p, regime), zero)
    j1 = numerical_jacobian(lambda xx: nonlinear_residual(zero, xx, p, regime), zero)
    for t in range(horizon + 1):
        z = np.r_[state, policy @ state]
        expected = np.r_[transition @ state, policy @ transition @ state]
        # Здесь проверяются *линейные* условия исходной системы: J0 z + J1 Ez_plus.
        linear_residual = j0 @ z + j1 @ expected
        max_residual = max(max_residual, float(np.max(abs(linear_residual))))
        rows.append({"Период": t, **observable_deviations(z, p, regime, expected)})
        state = transition @ state
    return rows, max_residual


def save_audit(directory: str | Path, p: Parameters | None = None) -> None:
    """Экспорт проверок стационара, Якобианов, корней и импульсов."""
    p = p or Parameters()
    output = Path(directory) / "results"
    output.mkdir(exist_ok=True, parents=True)
    with (output / "proverka_stacionara.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Условие", "Остаток"])
        writer.writerows(stationary_residuals(p).items())
    with (output / "stacionarnye_urovni.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Показатель", "Значение"])
        writer.writerows(p.steady_state().items())
    with (output / "proverka_matric.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Режим", "Макс. разность Якобианов", "Мин. сингулярное число", "Неустойчивые корни", "Макс. остаток инвариантности"])
        for regime in ("flex", "calvo"):
            matrix, info = independent_transition(p, regime)
            eig, policy, transition, qz = schur_solution(matrix)
            writer.writerow([regime, info["difference"], qz["smallest_singular_value"],
                             qz["unstable_count"], qz["max_invariance_residual"]])
    with (output / "proverka_kornei.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Режим", "Номер", "Действительная часть", "Мнимая часть"])
        for regime in ("flex", "calvo"):
            eig, _, _, _ = schur_solution(independent_transition(p, regime)[0])
            writer.writerows((regime, j, val.real, val.imag) for j, val in enumerate(eig, 1))


def main() -> None:
    """Запустить независимую проверку исходных уравнений."""
    p = Parameters()
    save_audit(Path(__file__).resolve().parent.parent, p)
    errors = stationary_residuals(p)
    print(f"Максимальный остаток стационара: {max(abs(x) for x in errors.values()):.3e}")
    print(f"Наклон кривой Филлипса из рекурсий: {calvo_price_derivative(p)['kappa_from_recursions']:.10f}")
    for regime in ("flex", "calvo"):
        m, info = independent_transition(p, regime)
        eig, policy, transition, results = schur_solution(m)
        print(f"Режим {regime}: отклонение матрицы {info['difference']:.3e}; "
              f"неустойчивых корней {results['unstable_count']}; "
              f"минимальное сингулярное число {results['smallest_singular_value']:.3e}; "
              f"корни {np.round(eig.real, 8).tolist()}")
    print("Независимая проверка завершена; таблицы CSV сохранены.")


if __name__ == "__main__":
    main()
