#!/usr/bin/env python3
"""Generate publication-quality figures for the LLM-GridEval paper."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

# ACM style settings
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Helvetica', 'Arial', 'DejaVu Sans'],
    'font.size': 8,
    'axes.labelsize': 8,
    'axes.titlesize': 8,
    'xtick.labelsize': 7,
    'ytick.labelsize': 7,
    'legend.fontsize': 7,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.02,
})

OUT = Path(__file__).parent


def figure2_evg_barchart():
    """Figure 2: EVG bar chart across operating points."""
    ops = ['Hour 4\n(Low Load)', 'Hour 7\n(Medium Load)', 'Hour 14\n(High Load)']
    random_tvd = [60, 75, 295]
    v1_tvd = [48, 120, 295]
    v2_tvd = [135, 180, 295]
    random_std = [49, 30, 0]
    v1_std = [27, 0, 0]
    v2_std = [30, 0, 0]
    evg_labels = ['2.25×', '2.40×', '1.0×']
    sig_labels = ['*', '***', '']

    x = np.arange(len(ops))
    width = 0.22
    gap = 0.02

    fig, ax = plt.subplots(figsize=(3.33, 2.0))

    bars_r = ax.bar(x - width - gap, random_tvd, width, yerr=random_std,
                    color='#9E9E9E', edgecolor='#666666', linewidth=0.5,
                    capsize=2, error_kw={'linewidth': 0.75}, label='Random', zorder=3)
    bars_v1 = ax.bar(x, v1_tvd, width, yerr=v1_std,
                     color='#4285F4', edgecolor='#2962FF', linewidth=0.5,
                     capsize=2, error_kw={'linewidth': 0.75}, label='AI-V1 (Timing)',
                     hatch='///', zorder=3)
    bars_v2 = ax.bar(x + width + gap, v2_tvd, width, yerr=v2_std,
                     color='#EA4335', edgecolor='#C62828', linewidth=0.5,
                     capsize=2, error_kw={'linewidth': 0.75}, label='AI-V2 (Strategy)',
                     hatch='xx', zorder=3)

    # EVG labels above V2 bars
    for i, (bar, label) in enumerate(zip(bars_v2, evg_labels)):
        y = bar.get_height() + (v2_std[i] if v2_std[i] > 0 else 5)
        ax.text(bar.get_x() + bar.get_width()/2, y + 8, label,
                ha='center', va='bottom', fontsize=7, fontweight='bold', color='#C62828')

    # Significance brackets
    for i, sig in enumerate(sig_labels):
        if sig:
            x_r = x[i] - width - gap
            x_v2 = x[i] + width + gap
            y_max = max(random_tvd[i] + random_std[i], v2_tvd[i] + v2_std[i]) + 20
            ax.plot([x_r, x_r, x_v2, x_v2], [y_max, y_max + 8, y_max + 8, y_max],
                    color='black', linewidth=0.75, zorder=4)
            ax.text((x_r + x_v2) / 2, y_max + 10, sig,
                    ha='center', va='bottom', fontsize=7, fontweight='bold')

    # Ceiling line
    ax.axhline(y=295, color='#666666', linestyle='--', linewidth=0.75, zorder=2)
    ax.text(2.55, 298, 'Experiment ceiling', fontsize=7, fontweight='bold', fontstyle='italic',
            color='#444444', ha='right', va='bottom')

    ax.set_ylabel('TVD (seconds)')
    ax.set_xticks(x)
    ax.set_xticklabels(ops)
    ax.set_ylim(0, 340)
    ax.set_yticks(range(0, 350, 50))
    ax.yaxis.grid(True, linewidth=0.3, color='#E0E0E0', zorder=1)
    ax.set_axisbelow(True)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(loc='upper left', framealpha=0.9, edgecolor='#CCCCCC')

    fig.savefig(OUT / 'fig2_evg_barchart.pdf')
    fig.savefig(OUT / 'fig2_evg_barchart.png')
    print(f'Figure 2 saved to {OUT / "fig2_evg_barchart.pdf"}')
    plt.close(fig)


def figure3_timelines():
    """Figure 3: Attack timeline comparison at Hour 7 (placeholder with approximate data)."""
    fig, axes = plt.subplots(3, 1, figsize=(3.33, 2.4), sharex=True)

    t = np.arange(0, 301, 5)
    threshold = 4200

    # Approximate power traces (simplified from experiment data)
    # Random: brief spikes
    p_random = np.full_like(t, 3700.0, dtype=float)
    p_random[0:3] += 800  # Attack 1 at t=0
    p_random[3:6] -= 200  # Controller response
    p_random[22:25] += 1400  # Attack 2 at t=110
    p_random[25:28] -= 400
    p_random[44:47] += 1100  # Attack 3 at t=220
    p_random[47:50] -= 300

    # V1: repeated single-EV spikes
    p_v1 = np.full_like(t, 3700.0, dtype=float)
    p_v1[6:9] += 1500   # Attack 1 at t=30
    p_v1[9:12] -= 500
    p_v1[26:29] += 1500  # Attack 2 at t=130
    p_v1[29:32] -= 500
    p_v1[58:61] += 1500  # Attack 3 at t=290

    # V2: staircase accumulation
    p_v2 = np.full_like(t, 3700.0, dtype=float)
    for start, delta in [(0, 1500), (18, 1500), (36, 1500), (56, 1500)]:
        end = min(start + 8, len(t))
        p_v2[start:end] += delta
        if end < len(t):
            p_v2[end:] += delta * 0.3  # Partial retention

    panels = [
        ('(a) Random (TVD = 75 s)', p_random, [(0, 'EV1'), (110, 'EV1'), (220, 'EV2')]),
        ('(b) AI-V1 Timing (TVD = 120 s)', p_v1, [(30, 'EV1'), (130, 'EV1'), (290, 'EV1')]),
        ('(c) AI-V2 Strategy (TVD = 180 s)', p_v2, [(0, 'EV1'), (90, 'EV2'), (180, 'EV3'), (280, 'EV4')]),
    ]

    for ax, (title, power, attacks) in zip(axes, panels):
        ax.plot(t, power, color='black', linewidth=0.8, zorder=3)
        ax.axhline(y=threshold, color='#EA4335', linestyle='--', linewidth=0.75, zorder=2)
        ax.fill_between(t, threshold, power, where=(power >= threshold),
                        color='#EA4335', alpha=0.15, zorder=2)

        for at, label in attacks:
            ax.annotate('▲', xy=(at, 2600), fontsize=5, color='#EA4335',
                        ha='center', va='bottom', zorder=4)
            ax.text(at, 2700, label, fontsize=4, color='#EA4335', ha='center', va='bottom')

        ax.set_ylabel('kW', fontsize=6)
        ax.set_ylim(2500, 6500)
        ax.set_yticks([3000, 4000, 5000, 6000])
        ax.yaxis.grid(True, linewidth=0.2, color='#E0E0E0')
        ax.set_axisbelow(True)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.text(5, 6200, title, fontsize=7, fontweight='bold', va='top')

    axes[-1].set_xlabel('Time (seconds)')
    axes[-1].set_xlim(0, 300)
    axes[-1].set_xticks([0, 60, 120, 180, 240, 300])

    # Threshold label on first panel only
    axes[0].text(295, 4300, '4200 kW', fontsize=5, color='#EA4335', ha='right')

    plt.subplots_adjust(hspace=0.15)
    fig.savefig(OUT / 'fig3_timelines.pdf')
    fig.savefig(OUT / 'fig3_timelines.png')
    print(f'Figure 3 saved to {OUT / "fig3_timelines.pdf"}')
    plt.close(fig)


if __name__ == '__main__':
    figure2_evg_barchart()
    figure3_timelines()
    print('All figures generated.')
