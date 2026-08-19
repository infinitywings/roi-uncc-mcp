# Superseded timing map

This create-once analysis is preserved for audit history. Its statistical,
completion, missingness, and token-limit results are unchanged and correct.
Its static controller timing map incorrectly treated the frozen loop's
request for current logical time `t=0` as a grant at zero.

The live HELICS 3.6.1 cadence probe demonstrated that the request advances to
the first 60-second grant. The first correction was written to
`reanalysis_r2/`. A subsequent audit identified the GridLAB-D 60-second
periods and 60/120-second minimum-timestep constraints. The current canonical
analysis is:

- `../reanalysis_r4/v2_reanalysis.json`
- `../reanalysis_r4/completion_matrix.csv`
- `../cadence_probe_r1/cadence_probe.json`

No original output was overwritten.
