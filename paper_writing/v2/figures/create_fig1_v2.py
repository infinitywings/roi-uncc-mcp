#!/usr/bin/env python3
"""Figure 1: LLM-GridEval Architecture Diagram (v2 — clean, legible)."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Helvetica', 'Arial', 'DejaVu Sans'],
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.04,
})

fig, ax = plt.subplots(figsize=(3.33, 2.15))
ax.set_xlim(0, 3.33)
ax.set_ylim(0, 2.15)
ax.axis('off')

# ── Layer Backgrounds ──
bands = [
    (0.04, 1.58, 2.85, 0.52, '#E8F0FE'),  # Cognitive (top)
    (0.04, 0.88, 2.85, 0.64, '#FFF8E1'),   # Interface (middle)
    (0.04, 0.04, 2.85, 0.78, '#E8F5E9'),   # Co-sim (bottom)
]
for x, y, w, h, c in bands:
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02",
                 facecolor=c, edgecolor='none', zorder=0))

# ── Right Annotations ──
annots = [
    (2.97, 1.84, 'Reasoning\n& Planning', '#1565C0'),
    (2.97, 1.20, 'Constrained\nInterface', '#F57F17'),
    (2.97, 0.43, 'Physics\n& Control', '#2E7D32'),
]
for x, y, txt, c in annots:
    ax.text(x, y, txt, fontsize=5.5, fontweight='bold', ha='left', va='center',
            color=c, linespacing=1.2)

# ── Helper: draw a rounded box with multi-line text ──
def box(x, y, w, h, lines, fc='white', ec='#555555', fontsizes=None, bolds=None, colors=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.015",
                 facecolor=fc, edgecolor=ec, linewidth=0.5, zorder=2))
    n = len(lines)
    for i, line in enumerate(lines):
        yy = y + h/2 + (n/2 - 0.5 - i) * (h / (n + 0.8))
        fs = fontsizes[i] if fontsizes else 7
        fw = 'bold' if (bolds and bolds[i]) else 'normal'
        cl = colors[i] if colors else 'black'
        ax.text(x + w/2, yy, line, fontsize=fs, fontweight=fw, color=cl,
                ha='center', va='center', zorder=3)

def arrow(x1, y1, x2, y2, label='', lx=0, ly=0):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color='black', lw=0.7),
                zorder=4)
    if label:
        ax.text(x1 + lx, y1 + ly, label, fontsize=5, ha='left', va='center',
                color='#333333', fontstyle='italic', zorder=5)

# ═══════════════════════════════════════════════════
# COGNITIVE LAYER (top band)
# ═══════════════════════════════════════════════════

# Main LLM box
box(1.05, 1.65, 1.15, 0.38,
    ['LLM-based Attacker', 'Policy π'],
    fontsizes=[8, 7], bolds=[True, False])

# Swappable policies (dashed box)
dx = FancyBboxPatch((0.1, 1.67), 0.82, 0.34, boxstyle="round,pad=0.015",
                    facecolor='white', edgecolor='#999999', linewidth=0.5,
                    linestyle='--', zorder=1)
ax.add_patch(dx)
ax.text(0.51, 1.99, 'Swappable', fontsize=5, ha='center', va='bottom',
        color='#777777', fontstyle='italic')
colors_sw = ['#9E9E9E', '#4285F4', '#EA4335']
labels_sw = ['Random', 'AI-V1', 'AI-V2']
for i, (lbl, c) in enumerate(zip(labels_sw, colors_sw)):
    bx = 0.14 + i * 0.26
    box(bx, 1.70, 0.24, 0.18, [lbl], fc=c, ec=c,
        fontsizes=[6], colors=['white' if c != '#9E9E9E' else 'black'])

# ═══════════════════════════════════════════════════
# INTERFACE LAYER (middle band)
# ═══════════════════════════════════════════════════

# MCP Server box
box(0.15, 0.96, 1.55, 0.48,
    ['MCP HTTP Server', '(FastAPI + HELICS federate)'],
    fontsizes=[8, 6], bolds=[True, False])

# Tool boxes inside
box(0.2, 0.98, 0.65, 0.22,
    ['get_status()', 'read state'],
    fc='#FFFDE7', fontsizes=[6.5, 5], bolds=[True, False])
box(0.92, 0.98, 0.72, 0.22,
    ['set_capacity()', 'write EV power'],
    fc='#FFFDE7', fontsizes=[6.5, 5], bolds=[True, False])

# Constraints box
box(1.85, 0.96, 0.85, 0.48,
    ['Constraints', 'bounds · cooldown', 'ramp rate'],
    fc='#FFF9C4', fontsizes=[7, 5.5, 5.5], bolds=[True, False, False])

# ═══════════════════════════════════════════════════
# CO-SIMULATION LAYER (bottom band)
# ═══════════════════════════════════════════════════

feds = [
    (0.08,  ['GridPACK', 'IEEE 9-bus', '5 s']),
    (0.78,  ['GridLAB-D', 'Feeder A+EVs', '60 s']),
    (1.48,  ['GridLAB-D', 'Feeder B', '120 s']),
    (2.18,  ['Controller v2', 'Defense M', '10 s']),
]
for x, lines in feds:
    box(x, 0.30, 0.62, 0.42, lines,
        fc='#C8E6C9', fontsizes=[7, 6, 5],
        bolds=[True, False, False],
        colors=['black', 'black', '#666666'])

# HELICS bar
ax.add_patch(FancyBboxPatch((0.08, 0.08), 2.72, 0.16, boxstyle="round,pad=0.01",
             facecolor='#81C784', edgecolor='#555555', linewidth=0.5, zorder=2))
ax.text(1.44, 0.16, 'HELICS value exchange (voltages, powers)',
        fontsize=6, ha='center', va='center', fontweight='bold', color='#1B5E20', zorder=3)

# Arrows between bands
arrow(1.40, 1.65, 1.10, 1.48, 'Tool calls (JSON)', lx=0.03, ly=-0.07)
arrow(1.90, 1.48, 2.10, 1.65, 'Observations', lx=0.03, ly=0.03)
arrow(0.93, 0.96, 0.93, 0.75, 'HELICS API', lx=0.03, ly=-0.07)
arrow(1.85, 0.75, 1.85, 0.96, 'Measurements', lx=0.03, ly=0.03)

fig.savefig(OUT / 'fig1_architecture.pdf')
fig.savefig(OUT / 'fig1_architecture.png')
print(f'Figure 1 saved')
plt.close(fig)

if __name__ == '__main__':
    pass
