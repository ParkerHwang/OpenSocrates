"""Static figures from the corrected, retained observations only."""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / "summary.json").read_text())
assert len([x for x in data["cells"] if x["stage"] == 3]) == 81
arms = ["vanilla", "v1.4.0", "v1.5.0-rc"]
labels = ["Vanilla Codex", "OpenSocrates 1.4", "OpenSocrates 1.5 RC*"]
colors = ["#4477AA", "#228866", "#BB6677"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold"})


def group(arm, workload, concurrency, rate):
    return next(x for x in data["groups"] if (x["arm"], x["stage"], x["workload"], x["concurrency"], x["rate"]) == (arm, 3, workload, concurrency, rate))


fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.8))
plots = [(axes[0, 0], "read", "http_success_rps", "Read throughput", "Successful HTTP requests / s"), (axes[0, 1], "lifecycle", "completed_jobs_per_second", "Claim + durable completion", "Completed jobs / s")]
for ax, workload, metric, title, ylabel in plots:
    for arm, label, color in zip(arms, labels, colors):
        stats = [group(arm, workload, n, 0)[metric] for n in (1, 16, 64)]
        y = np.array([s["median"] for s in stats])
        errors = [y - np.array([s["min"] for s in stats]), np.array([s["max"] for s in stats]) - y]
        ax.errorbar([0, 1, 2], y, yerr=errors, color=color, label=label, marker="o", capsize=4, linewidth=2, linestyle="--" if arm == arms[-1] else "-")
    ax.set(xticks=[0, 1, 2], xticklabels=["1", "16", "64"], xlabel="Concurrent clients", ylabel=ylabel, title=title, ylim=(0, None))
    ax.grid(axis="y", alpha=.15)
ax = axes[1, 0]
for arm, label, color in zip(arms, labels, colors):
    stats = [group(arm, "read", 1, rate)["scheduled_p99_ms"] for rate in (100, 500, 1000)]
    y = np.array([s["median"] for s in stats])
    ax.errorbar([0, 1, 2], y, yerr=[y - np.array([s["min"] for s in stats]), np.array([s["max"] for s in stats]) - y], color=color, marker="o", capsize=4, linewidth=2, linestyle="--" if arm == arms[-1] else "-")
ax.set(xticks=[0, 1, 2], xticklabels=["100", "500", "1000"], xlabel="Fixed scheduled requests / s", ylabel="p99 from scheduled arrival (ms)", title="Read tail latency, including dispatch lag", ylim=(0, None))
ax.grid(axis="y", alpha=.15)
ax = axes[1, 1]
for i, (arm, color) in enumerate(zip(arms, colors)):
    y = [group(arm, work, 64, 0)["server_peak_rss_mib"]["median"] for work in ("read", "lifecycle")]
    ax.bar(np.arange(2) + (i - 1) * .24, y, width=.22, color=color, hatch="//" if arm == arms[-1] else None)
ax.set(xticks=[0, 1], xticklabels=["Read, concurrency 64", "Lifecycle, concurrency 64"], ylabel="Median process peak RSS (MiB)", title="Server memory over the full process lifetime")
ax.grid(axis="y", alpha=.15)
fig.suptitle("QueueForge — three fixed-condition backend artifacts", x=.06, ha="left", fontsize=19, weight="bold")
fig.legend(*axes[0, 0].get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(.51, .948), ncol=3, frameon=False)
fig.text(.06, .037, "Points: median; whiskers: observed min–max across 3 load repeats. One generated implementation per condition.\n*1.5 RC passed 19 API scenarios but retained one failing self-test; its performance remains diagnostic.\nShared Apple-silicon Mac, SQLite WAL / synchronous=FULL, 50,000 jobs, 256-byte payload; corrected meter v2.", fontsize=9, color="#444444")
fig.tight_layout(rect=(.035, .10, .985, .90))
fig.savefig(HERE / "performance.png", dpi=170)
plt.close(fig)

fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.8))
x = np.arange(3)
totals = [data["development_totals"][a] for a in arms]
minutes = [r["model_seconds"] / 60 for r in totals]
axes[0].bar(x, minutes, color=colors)
axes[0].set(ylabel="Summed invocation wall minutes", title="Development time")
cached = [r["usage"]["cached_input_tokens"] / 1e6 for r in totals]
uncached = [r["uncached_input_tokens"] / 1e6 for r in totals]
axes[1].bar(x, cached, color=colors, alpha=.4, label="Cached input")
axes[1].bar(x, uncached, bottom=cached, color=colors, label="Uncached input")
axes[1].set(ylabel="Reported input tokens (millions)", title="Input work, with cached subset")
axes[1].legend(frameon=False, fontsize=8)
axes[2].bar(x, [r["tool_actions"] for r in totals], color=colors)
axes[2].set(ylabel="Started or completed tool actions", title="Tool activity")
for ax in axes:
    ax.set(xticks=x, xticklabels=["Vanilla", "1.4", "1.5 RC*"])
    ax.grid(axis="y", alpha=.15)
fig.suptitle("Three fresh development sessions per condition", x=.06, ha="left", fontsize=18, weight="bold")
fig.text(.06, .035, "Same requested gpt-6-sol / medium / codex-cli 0.158.0-alpha.2. All 9 calls completed; no outcome retries.\nThese are observed work measures, not billed cost or a causal efficiency estimate. Preparation-agent usage is unavailable.\n*1.5 RC retained one failing self-test despite passing the external API scenarios.", fontsize=9, color="#444444")
fig.tight_layout(rect=(.03, .12, .985, .88))
fig.savefig(HERE / "development.png", dpi=170)
plt.close(fig)
