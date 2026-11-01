"""Воспроизводимые импульсные отклики и сохранение отдельных графиков."""

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.model import (Parameters, observable_deviations,
                       stable_solution, transition_matrix)


VARIABLES = {
    "Выпуск": ("vypusk", r"$\widehat{y}_t$"),
    "Потребление": ("potreblenie", r"$\widehat{c}_t$"),
    "Инвестиции": ("investicii", r"$\widehat{I}_t$"),
    "Труд": ("trud", r"$\widehat{n}_t$"),
    "Капитал": ("kapital", r"$\widehat{k}_t$"),
    "Инфляция": ("inflyaciya", r"$\pi_t$"),
    "Номинальная ставка": ("nominalnaya_stavka", r"$\widetilde{i}_t$"),
    "Ожидаемая реальная ставка": ("realnaya_stavka", r"$\widetilde{r}_t$"),
    "Реальные денежные остатки": ("denezhnye_ostatki", r"$\widehat{m}_t$"),
    "Реальная заработная плата": ("zarplata", r"$\widehat{w}_t$"),
    "Арендная ставка капитала": ("arenda_kapitala", r"$\widehat{r}_t^k$"),
    "Предельные издержки": ("predelnye_izderzhki", r"$\widehat{mc}_t$"),
}


def impulses(p: Parameters, regime: str, shock: str,
             horizon: int = 40) -> list[dict[str, float]]:
    """Отклики на однократную инновацию в начале первого периода."""
    matrix = transition_matrix(p, regime)
    _, policy, transition = stable_solution(matrix)
    state = np.zeros(3)
    if shock == "technology":
        state[1] = 0.01  # Один процент логарифмической производительности.
    elif shock == "monetary":
        state[2] = 0.0025  # 0,25 процентного пункта валовой ставки в логарифмах.
    else:
        raise ValueError("Неизвестный шок.")
    rows = []
    for t in range(horizon + 1):
        full = np.concatenate([state, policy @ state])
        predicted = matrix @ full
        observed = observable_deviations(full, p, regime, predicted)
        rows.append({"Период": t, **observed})
        state = transition @ state
    return rows


def save_results(directory: str | Path, p: Parameters | None = None,
                 horizon: int = 40) -> None:
    """Создать таблицы и отдельные рисунки в формате SVG."""
    p = p or Parameters()
    root = Path(directory)
    results = root / "results"
    figures = root / "figures"
    results.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    labels = {"calvo": "Цены по Кальво", "flex": "Гибкие цены"}
    shocks = {"technology": "Технологический шок (+1 %)",
              "monetary": "Шок денежной политики (+0,25 п. п.)"}
    for shock, shock_title in shocks.items():
        records = {regime: impulses(p, regime, shock, horizon)
                   for regime in ("flex", "calvo")}
        for regime, rows in records.items():
            path = results / f"otkliki_{shock}_{regime}.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        for name, (slug, symbol) in VARIABLES.items():
            fig, ax = plt.subplots(figsize=(7.2, 4.6))
            for regime in ("flex", "calvo"):
                rows = records[regime]
                ax.plot([row["Период"] for row in rows],
                        [100 * row[name] for row in rows],
                        linewidth=2, label=labels[regime])
            ax.axhline(0, linewidth=0.8, color="gray")
            ax.set_title(f"{name}: {shock_title}")
            ax.set_xlabel("Период после шока")
            ax.set_ylabel(f"{symbol}, отклонение × 100")
            ax.grid(alpha=0.25)
            ax.legend()
            fig.tight_layout()
            fig.savefig(figures / f"{shock}_{slug}.svg", format="svg")
            plt.close(fig)


def main() -> None:
    """Печать диагностик и генерация результатов."""
    root = Path(__file__).resolve().parent.parent
    p = Parameters()
    steady = p.steady_state()
    print("Стационарные соотношения:")
    for key in ("rk", "i_nom", "mc", "k_y", "s_i", "s_c"):
        print(f"  {key}: {steady[key]:.10f}")
    for regime in ("flex", "calvo"):
        matrix = transition_matrix(p, regime)
        eigenvalues, policy, _ = stable_solution(matrix)
        print(f"Режим: {regime}; корни: {np.round(eigenvalues.real, 8).tolist()}")
        print(f"Число нестабильных корней: {sum(abs(eigenvalues) > 1)}")
        print(f"Размерность решения: {policy.shape}")
    save_results(root, p)
    print("Таблицы CSV и отдельные графики SVG сохранены.")


if __name__ == "__main__":
    main()
