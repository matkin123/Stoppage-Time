# Headline X% sensitivity to the BIP threshold (standalone, locked tables untouched)

Re-runs s03->s07->s08 at each `max_live_gap_s` and reads the CENTRAL spec (`silent_marked|overall|pooled_all|hl=4.0|on`, window 1H+2H). Central 20s row matches the locked ADR-0025 headline.

| max_live_gap | gate | both anchors ±90s | scoreline X% | 95% CI | Δ vs 20s (pp) | flip X% |
|---|---|---|---|---|---|---|
| 12s | fail | no | 23.51% | [20.3, 27.3] | -0.10 | 11.98% |
| 14s | ok | yes | 23.57% | [20.4, 27.3] | -0.04 | 12.04% |
| 16s | ok | yes | 23.61% | [20.4, 27.4] | -0.00 | 12.07% |
| 18s | ok | yes | 23.62% | [20.4, 27.4] | +0.01 | 12.09% |
| 20s **(central)** | ok | yes | 23.61% | [20.4, 27.4] | +0.00 | 12.11% |
| 22s | ok | no | 23.63% | [20.5, 27.4] | +0.02 | 12.10% |
| 24s | ok | no | 23.61% | [20.4, 27.4] | -0.00 | 12.09% |
| 26s | ok | no | 23.63% | [20.5, 27.4] | +0.02 | 12.09% |
| 28s | ok | no | 23.63% | [20.5, 27.4] | +0.02 | 12.09% |
| 30s | ok | no | 23.66% | [20.5, 27.4] | +0.05 | 12.11% |

**Full sweep (12-30s):** scoreline 23.51-23.66%, flip 11.98-12.11%. 
**In-tolerance band (14-20s, both anchors within Opta ±90s):** scoreline 23.57-23.62% (max deviation 0.04 pp from the 20s central), flip 12.04-12.11%.

_The 95% CIs above are recomputed with the s08 grid trimmed to the central silent/conditioning/source axes, so the bootstrap RNG-stream position differs slightly from the full-grid production run. The DETERMINISTIC central point (20s -> 23.61% ≈ the locked 23.6%) reproduces ADR-0025 exactly; only the CI lower rail lands ~0.2 pp off the locked [20.6, 27.4] purely from stream position, not from any change to the model._

The headline barely moves because BIP enters the counterfactual in two offsetting places: the per-live-minute scoring rate `lambda = G/L` (live-minutes in the denominator) and the omitted-live exposure `D x (L/T)` (live-share in the numerator), so `mu ~= lambda x omitted_live = G x D / T` and the live-minutes `L` largely cancel. The residual deviation is the second-order gross-up/decay nonlinearity.
