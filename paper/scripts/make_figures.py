"""Generate English-language publication figures from the verified IRF CSV outputs."""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / "paper" / "figures"
VARIABLES = {
    "output": ("Выпуск", "Output", r"$\hat y_t$"),
    "consumption": ("Потребление", "Consumption", r"$\hat c_t$"),
    "investment": ("Инвестиции", "Investment", r"$\hat I_t$"),
    "hours": ("Труд", "Hours worked", r"$\hat n_t$"),
    "inflation": ("Инфляция", "Inflation", r"$\pi_t$"),
    "nominal_rate": ("Номинальная ставка", "Nominal interest rate", r"$\widetilde i_t$"),
}
SHOCKS = {
    "technology": "Positive technology innovation (0.01 log units)",
    "monetary": "Positive policy-rule innovation (0.0025 log units)",
}


def read_irfs(shock: str, regime: str) -> list[dict[str, str]]:
    path = ROOT / "results" / f"otkliki_{shock}_{regime}.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 41 or [int(row["Период"]) for row in rows] != list(range(41)):
        raise ValueError(f"Unexpected time index: {path}")
    return rows


def generate() -> None:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.family": "DejaVu Serif", "font.size": 9.5,
        "mathtext.fontset": "dejavuserif", "svg.fonttype": "path", "svg.hashsalt": "dsge-miu-calvo-paper",
        "axes.spines.top": False, "axes.spines.right": False,
        "savefig.facecolor": "white",
    })
    for shock, shock_label in SHOCKS.items():
        records = {regime: read_irfs(shock, regime) for regime in ("flex", "calvo")}
        for key, (column, title, symbol) in VARIABLES.items():
            fig, ax = plt.subplots(figsize=(6.7, 3.25))
            t = np.arange(41)
            for regime, label, color, style in (
                ("flex", "Flexible prices", "#1f4e79", "-"),
                ("calvo", "Calvo pricing", "#be4a2f", "--"),
            ):
                values = np.asarray([float(row[column]) for row in records[regime]])
                ax.plot(t, 100 * values, color=color, lw=2, ls=style, label=label)
            ax.axhline(0, color="#666666", lw=0.65)
            ylabel = ("Percentage points" if key in ("inflation", "nominal_rate")
                      else "Log deviation (percent)")
            ax.set(xlabel="Quarters after the shock", ylabel=ylabel,
                   title=f"{title}: {shock_label}")
            ax.grid(alpha=0.17)
            ax.legend(frameon=False, loc="best", fontsize=9)
            ax.set_xlim(0, 40)
            fig.tight_layout(pad=1.0)
            fig.savefig(DESTINATION / f"{shock}_{key}.svg", format="svg", metadata={"Date": None})
            plt.close(fig)


if __name__ == "__main__":
    generate()
    print("English-language SVG figures generated from verified CSV outputs.")
