"""Static descriptive figure; no imputation, inferential bars or model ranking."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent


def main():
    rows = json.loads((HERE / "summary.json").read_text())["rows"]
    tuples = ["sol-medium", "luna-medium", "luna-max"]
    arms = ["vanilla", "v14", "v15"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.3))
    fig.patch.set_facecolor("#FAFBFC")
    cmap = plt.colormaps["YlGnBu"].copy()
    cmap.set_bad("#E5E7EB")
    for axis, task, maximum in zip(axes, ["coding", "office"], [28, 27], strict=True):
        selected = {(r["tuple"], r["arm"]): r for r in rows if r["task"] == task}
        values = np.array(
            [
                [
                    selected[t, a]["passed_checks"] / maximum
                    if selected[t, a]["passed_checks"] is not None
                    else np.nan
                    for a in arms
                ]
                for t in tuples
            ]
        )
        axis.imshow(values, vmin=0, vmax=1, cmap=cmap, aspect="auto")
        for i, t in enumerate(tuples):
            for j, a in enumerate(arms):
                row = selected[t, a]
                checks = (
                    f"{row['passed_checks']}/{maximum}"
                    if row["passed_checks"] is not None
                    else "Unassessable"
                )
                if task == "coding" and row["own_tests_pass"] is False:
                    checks += " !"
                elapsed = (
                    f"{row['wall_seconds'] / 60:.1f} min"
                    if row["wall_seconds"] is not None
                    else "No timing"
                )
                if row["timed_out"]:
                    elapsed += " *"
                color = "white" if values[i, j] >= 0.65 else "#172033"
                axis.text(
                    j,
                    i - 0.12,
                    checks,
                    ha="center",
                    va="center",
                    color=color,
                    fontsize=14,
                    weight="bold",
                )
                axis.text(j, i + 0.18, elapsed, ha="center", va="center", color=color, fontsize=11)
        axis.set_xticks(
            range(3), ["Vanilla", "OpenSocrates\n1.4", "OpenSocrates\n1.5 RC"], fontsize=10
        )
        axis.set_yticks(range(3), ["Sol medium", "Luna medium", "Luna max"], fontsize=11)
        axis.set_title(
            "Backend coding" if task == "coding" else "Korean office work",
            loc="left",
            fontsize=15,
            pad=16,
            weight="bold",
        )
        for spine in axis.spines.values():
            spine.set_visible(False)
        axis.tick_params(length=0, pad=9)
        axis.set_xticks(np.arange(-0.5, 3, 1), minor=True)
        axis.set_yticks(np.arange(-0.5, 3, 1), minor=True)
        axis.grid(which="minor", color="white", linewidth=3)
        axis.tick_params(which="minor", bottom=False, left=False)
    fig.suptitle(
        "Hard tasks: frozen checks and episode time",
        x=0.03,
        ha="left",
        fontsize=19,
        weight="bold",
        color="#172033",
    )
    fig.text(
        0.03,
        0.075,
        "One episode per cell. Checks are grouped artifact checks, not a general quality score.",
        fontsize=10,
        color="#374151",
    )
    fig.text(
        0.03,
        0.035,
        "* 20-minute timeout. ! Own tests fail. Times may overlap other generation work.",
        fontsize=10,
        color="#374151",
    )
    fig.subplots_adjust(left=0.115, right=0.985, top=0.80, bottom=0.20, wspace=0.37)
    fig.savefig(HERE / "comparison.png", dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)


if __name__ == "__main__":
    main()
