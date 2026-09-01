# GridEval/G7 roadmap artifact index

This directory is a design-only, non-executable research artifact. The original
roadmap mission is `mis_01M1AYNQJDB5D6VK2ZYN7V7011`; revision r2 implements the
interactive-attacker design requested under
`mis_01KYMRDZHYN4QXC1XFTGP54E36`.

Revision r2 adds the IA0–IA5 orchestration ladder, nine IA4/IA5 ablations, a
typed-tool parity contract, and the primary `IA4 − IA3` contrast. These changes
are roadmap/development-screening definitions; they do not amend the frozen
confirmatory experiment specification or its 384-run accounting.

The portable report is the frozen r2 design snapshot. Subsequent implementation
evidence is maintained outside the generated report: M4 one-turn model replay
is documented in `../M4_MODEL_REPLAY_REPORT.md`, and the offline M5 interactive
tool-loop protocol is documented in `../M5_INTERACTIVE_PROTOCOL_REPORT.md`.
The bounded two-turn M6 model qualification is documented in
`../M6_INTERACTIVE_MODEL_REPORT.md`.
The preregistered M7 mirrored counterfactual tool-use qualification is
documented in `../M7_COUNTERFACTUAL_TOOL_USE_REPORT.md`.
The M8 CAREER-alignment decision and subtle single-aggregator setpoint-bias
contract are documented in `../M8_CAREER_STEALTH_BIAS_DESIGN.md`. M8 narrows
the committed primary causal comparison to two action intervals and exactly one
midpoint revision; the broader IA0–IA5 ladder remains an extension and a
secondary method scaffold. This correction is maintained outside the frozen r2
portable report.
This separation avoids rewriting the report's original source manifest while
keeping current protocol evidence explicit.

- `report.html` — primary portable technical report; r2 browser-verified at
  1440 px and 390 px with 23 manifest blocks, synchronized semantic fallback,
  static light/dark chart SVGs, and no horizontal overflow.
- `artifact.json` — canonical report input used to build `report.html`.
- `roadmap_blueprint.json` — machine-readable research and experiment blueprint.
- `roadmap_gate_depth.sql` — reproducible transformation for the report's single
  roadmap evidence-gate chart.
- `validation_receipt.json` — packaging and QA result.

The current shared portable reader renders its top bar at `100vw`, which creates
an 8 px desktop overflow when a vertical scrollbar is present. The final report
therefore carries one scoped `data-grideval-portable-overflow-fix` style. Preserve
that fix (or upstream the equivalent reader correction) when rebuilding.

The artifact does not authorize live co-simulation, detector fitting, GPU/model
calls, evaluation-seed access, or a campaign. Evaluation remains sealed and the
campaign remains on hold.
