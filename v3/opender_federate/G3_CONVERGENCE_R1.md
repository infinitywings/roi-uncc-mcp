# G3 OpenDER Physical-Loop Convergence

Verdict: **PASS**

Selected coarsest passing step: **10 s**

All responses are paired pulse-minus-null values at common adapter sample times. The 1-second arm is the convergence reference.

## Explicit tolerances

| Metric | Limit |
|---|---:|
| Local mapping residual | 0.1 VA |
| Device P response | 0.1 kW |
| Device Q response | 0.1 kvar |
| Voltage response vs 1 s | 0.0001 pu |
| Source P response vs 1 s | 2000 W |
| Source Q response vs 1 s | 2000 var |

## Arm summary

| Step | Pass | Pulse/null mapping residual (VA) | Voltage error (pu) | Source P/Q error |
|---:|:---:|---:|---:|---:|
| 1 | yes | 0.00490337 / 0 | 0 | 0 W / 0 var |
| 5 | yes | 0.00471578 / 0 | 1.13354e-13 | 1.74623e-08 W / 5.59259e-07 var |
| 10 | yes | 0.00471578 / 0 | 1.9148e-11 | 9.20217e-06 W / 7.95471e-05 var |
| 60 | no | 0.00130082 / 0 | 0.00398783 | 10481.5 W / 10976.4 var |

Common sample times: 120 s, 300 s, 480 s, 660 s, 780 s

## Failed gates

- 60 s: `voltage_response_converges_to_1s`
- 60 s: `source_p_response_converges_to_1s`
- 60 s: `source_q_response_converges_to_1s`
