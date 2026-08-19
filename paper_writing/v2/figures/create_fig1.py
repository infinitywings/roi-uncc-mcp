#!/usr/bin/env python3
"""Generate Figure 1: LLM-GridEval Architecture Diagram."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Helvetica', 'Arial', 'DejaVu Sans'],
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.03,
})


def draw_box(ax, x, y, w, h, text, fontsize=7, color='white', edgecolor='#555555', bold=False):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02",
                         facecolor=color, edgecolor=edgecolor, linewidth=0.5)
    ax.add_patch(box)
    weight = 'bold' if bold else 'normal'
    ax.text(x + w/2, y + h/2, text, ha='center', va='center',
            fontsize=fontsize, fontweight=weight, wrap=True)


def draw_arrow(ax, x1, y1, x2, y2, label='', fontsize=5.5):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color='black', lw=0.75))
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx + 0.02, my, label, fontsize=fontsize, ha='left', va='center',
                fontstyle='italic', color='#333333')


fig, ax = plt.subplots(figsize=(3.33, 2.5))
ax.set_xlim(0, 3.33)
ax.set_ylim(0, 2.5)
ax.axis('off')

# Layer backgrounds
# Top: Cognitive (#E8F0FE)
ax.add_patch(FancyBboxPatch((0.05, 1.85), 2.95, 0.55, boxstyle="round,pad=0.02",
             facecolor='#E8F0FE', edgecolor='none'))
# Middle: Interface (#FFF8E1)
ax.add_patch(FancyBboxPatch((0.05, 1.1), 2.95, 0.65, boxstyle="round,pad=0.02",
             facecolor='#FFF8E1', edgecolor='none'))
# Bottom: Co-simulation (#E8F5E9)
ax.add_patch(FancyBboxPatch((0.05, 0.1), 2.95, 0.9, boxstyle="round,pad=0.02",
             facecolor='#E8F5E9', edgecolor='none'))

# Right annotations
ax.text(3.15, 2.12, 'Reasoning\n& Planning', fontsize=6, fontweight='bold',
        ha='center', va='center', color='#1565C0')
ax.text(3.15, 1.42, 'Typed,\nConstrained\nInterface', fontsize=6, fontweight='bold',
        ha='center', va='center', color='#F57F17')
ax.text(3.15, 0.55, 'Physics\n& Control', fontsize=6, fontweight='bold',
        ha='center', va='center', color='#2E7D32')

# === Cognitive Layer ===
draw_box(ax, 0.9, 1.95, 1.3, 0.35, 'LLM-based Attacker\n(Policy π)', fontsize=7,
         color='white', bold=True)

# Swappable policies (dashed box)
dashed = FancyBboxPatch((0.12, 1.97), 0.7, 0.30, boxstyle="round,pad=0.02",
                        facecolor='white', edgecolor='#888888', linewidth=0.5,
                        linestyle='dashed')
ax.add_patch(dashed)
ax.text(0.47, 2.22, 'Swappable', fontsize=5, ha='center', color='#666666', fontstyle='italic')
for i, (label, c) in enumerate([('Random', '#9E9E9E'), ('AI-V1', '#4285F4'), ('AI-V2', '#EA4335')]):
    draw_box(ax, 0.15 + i*0.22, 2.0, 0.2, 0.15, label, fontsize=5, color=c, edgecolor=c)

# === Interface Layer ===
draw_box(ax, 0.3, 1.22, 1.2, 0.4, '', fontsize=6, color='white')
ax.text(0.9, 1.55, 'MCP HTTP Server (FastAPI)', fontsize=6.5, ha='center',
        va='center', fontweight='bold')
draw_box(ax, 0.35, 1.25, 0.52, 0.2, 'get_grid_status()\nread feeder state',
         fontsize=5, color='#FFFDE7')
draw_box(ax, 0.92, 1.25, 0.55, 0.2, 'set_ev_capacity()\nwrite EV power',
         fontsize=5, color='#FFFDE7')

# Validation box
draw_box(ax, 1.7, 1.22, 0.95, 0.4, 'Validation &\nConstraints\nbounds · cooldown\nramping',
         fontsize=5.5, color='#FFF9C4')

# === Co-simulation Layer ===
feds = [
    ('GridPACK\nIEEE 9-bus\n(5 s)', 0.1, '#C8E6C9'),
    ('GridLAB-D\nFeeder A\n123-node+EVs\n(60 s)', 0.78, '#A5D6A7'),
    ('GridLAB-D\nFeeder B\n123-node\n(120 s)', 1.46, '#C8E6C9'),
    ('Controller v2\n(Defense M)\n(10 s)', 2.14, '#A5D6A7'),
]
for label, x, color in feds:
    draw_box(ax, x, 0.35, 0.62, 0.5, label, fontsize=5.5, color=color)

# HELICS bar
ax.add_patch(FancyBboxPatch((0.1, 0.15), 2.66, 0.15, boxstyle="round,pad=0.01",
             facecolor='#81C784', edgecolor='#555555', linewidth=0.5))
ax.text(1.43, 0.225, 'HELICS value exchange (voltages, powers)', fontsize=5.5,
        ha='center', va='center', fontweight='bold', color='#1B5E20')

# Arrows between layers
draw_arrow(ax, 1.2, 1.95, 1.0, 1.65, 'Tool calls\n(JSON)')
draw_arrow(ax, 1.6, 1.65, 1.8, 1.95, 'Observations')
draw_arrow(ax, 0.9, 1.2, 0.9, 0.88, 'HELICS API')
draw_arrow(ax, 1.8, 0.88, 1.8, 1.2, 'Measurements')

fig.savefig(OUT / 'fig1_architecture.pdf')
fig.savefig(OUT / 'fig1_architecture.png')
print(f'Figure 1 saved to {OUT / "fig1_architecture.pdf"}')
plt.close(fig)


if __name__ == '__main__':
    draw_box = draw_box  # ensure defined
    draw_arrow = draw_arrow
    exec(open(__file__).read().split("if __name__")[0] + "\nfig.savefig(OUT / 'fig1_architecture.pdf')\nfig.savefig(OUT / 'fig1_architecture.png')\nprint('Done')\nplt.close(fig)")
