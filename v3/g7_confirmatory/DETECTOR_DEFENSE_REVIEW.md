# Detector and defense shortlist for G7

Review date: 2026-08-31. This is a design shortlist, not a claim that every
method is already integrated or that any paper's reported accuracy transfers
to the current feeder.

The bounded LLM client disables Qwen thinking for schedule proposals so a
small, fixed generation allowance cannot be exhausted before final JSON. This
is a protocol-control choice, not a detector or attack advantage; all LLM-arm
requests use the same setting and log its hash.

## Recommended benchmark stack

### Tier 0: transparent baselines

1. **Rules and command envelope.** Validate authentication context, DER mode,
   P/Q capability, ramp, SOC, execution time, and safe voltage-dependent
   admissibility. This catches unsafe valid-looking commands before actuation.
2. **Physics residual / bad-data detector.** Retain VSCT/WLS as the canonical
   measurement-integrity baseline, but explicitly test its blindness when the
   malicious command and delivered P/Q agree.
3. **Sequential innovation detector.** Retain calibrated multivariate CUSUM for
   low-and-slow temporal accumulation. Report trajectory FAR and latency.

These are interpretable, cheap, and necessary controls even if a learned model
later wins.

### Tier 1: best near-term fit for this codebase

4. **Cross-layer command-response consistency detector.** Fuse intended benign
   dispatch, authenticated command, delivered P/Q, voltage response, mode,
   SOC, and saturation. This directly targets the current authority-abuse gap:
   physical consistency alone is insufficient when intent is malicious. Use a
   model residual plus a sequential score, with a separate policy-violation
   channel so the detector does not reduce to `command != benign`.
5. **Hybrid central physics + local unsupervised detector.** NREL demonstrates a
   central state-estimation residual combined with local inverter autoencoders
   on voltage/P/Q/DER data. This maps naturally to a cloud detector plus one
   small edge detector per OpenDER instance and gives a useful ablation against
   the current command-blind PCA reconstruction model.
6. **Temporal graph prediction detector.** Build nodes from feeder buses/DERs,
   edges from electrical topology, and temporal features from V/P/Q/SOC/mode.
   Compare GAT/GDN or GNN-LSTM prediction residuals with a topology-agnostic
   LSTM. PNNL's 2024 comparison found graph methods stronger than k-means and an
   autoencoder on several simulated attack types, while also exposing harder
   combined/riding-wave localization cases. That limitation is precisely a
   useful red-team target.

### Tier 2: active and adversarial defenses

7. **Physics-aware dynamic watermark / challenge-response.** Add a small,
   bounded private excitation to selected commands and test the expected
   physical response with a distributed observer. The 2024 UIO work explicitly
   co-designs watermark strength, observer, and control gains, and treats
   time-synchronization error. This is appropriate for white-box residual-
   consistent telemetry attacks, but it must be charged for voltage/control
   degradation.
8. **Event-triggered moving-target defense.** Trigger a safe configuration or
   challenge perturbation only after a passive suspicion score, then test
   whether the response matches the known physics. The published DDET-MTD work
   combines data and physics to reduce continuous-MTD cost; its public code is
   useful as a reference, although transmission-line D-FACTS actions are not a
   drop-in match for this distribution feeder.
9. **Malicious Volt-VAR curve screening.** A local pre-activation classifier or
   robust reachability check can reject oscillatory/unsafe curves before they
   reach the inverter. The learning-based 2023 work is a concrete comparator;
   for assurance, pair it with deterministic curve and stability constraints.
10. **Resilient local fallback.** On alarm or communication loss, freeze/decay
    remote commands and restore a locally verified Volt-VAR/Volt-Watt profile.
    Compare alarm-only, reject-command, and local-fallback responses so a
    detector's benefit is not confused with mitigation benefit.

## Black/gray/white detector tests

| Test | Attacker access | Required attack families | Main question |
|---|---|---|---|
| Black-box | No scores/thresholds/topology; noisy telemetry only | step, pulse, ramp, intermittent, riding-wave, subset | Does the detector generalize beyond its training family without leaking state? |
| Gray-box | Family known; approximate sensitivity; binary/delayed alarm | system-ID, schedule search, alarm-boundary search, model mismatch | How much does bounded reconnaissance reduce latency-adjusted security? |
| White-box | Exact feature/code/threshold/state and topology | residual-consistent FDI, adaptive CUSUM reset, AE/GNN adversarial optimization, compound command+concealment | What is the worst attainable harm under equal authority/query/energy budgets? |

Also test the defender under topology, load/PV, noise, latency, missing-sensor,
and device-model shifts. Thresholds must be fixed using only calibration data;
hyperparameters and model selection use development data; final comparison uses
the held-out evaluation partition exactly once.

## Selection recommendation

For the next implementation increment, use a four-member detector ensemble:

- current physics residual (VSCT/WLS);
- calibrated sequential CUSUM;
- local/central hybrid reconstruction or prediction residual; and
- cross-layer command-response/intent consistency.

Then add a temporal graph model as the principal learned challenger. Add
watermarking only after the passive stack and timing model are validated,
because an active detector changes the plant input and must be evaluated as a
defense with operational cost, not as a free detector.

The ensemble output should preserve individual scores and use a preregistered
fusion rule. Never tune fusion weights on confirmatory attacks.

## Primary sources

- PNNL, *Advancing Cyber-Attack Detection in Power Systems: A Comparative Study
  of Machine Learning and Graph Neural Network Approaches* (2024):
  https://arxiv.org/abs/2411.02248
- Sahu et al., *Detection of False Data Injection Attacks on Power Dynamical
  Systems With a State Prediction Method* (2024):
  https://arxiv.org/abs/2409.04609
- NREL, *A Hybrid Data-Driven and Model-Based Anomaly Detection Scheme for DER
  Operation* (2022): https://www.nrel.gov/docs/fy22osti/80628.pdf
- Liu et al., *Physics-aware watermarking embedded in unknown input observers
  for false data injection attack detection in cyber-physical microgrids*
  (IEEE TIFS, 2024): https://eprints.whiterose.ac.uk/id/eprint/216412/
- Xu et al., *Blending Data and Physics Against False Data Injection Attack: An
  Event-Triggered Moving Target Defence Approach* (IEEE TSG, 2023), code:
  https://github.com/xuwkk/DDET-MTD
- Saber et al., *Learning-Based Detection of Malicious Volt-VAr Control
  Parameters in Smart Inverters* (2023): https://arxiv.org/abs/2309.10304
- Zhen et al., *Admittance-Guided Inverter Dispatch Command Manipulation Attack*
  (2026 preprint; emerging threat model): https://arxiv.org/abs/2605.14509
- IEEE 1547.3-2023, *Guide for Cybersecurity of Distributed Energy Resources
  Interconnected with Electric Power Systems*:
  https://standards.ieee.org/ieee/1547.3/10173/
