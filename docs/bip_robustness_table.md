# BIP knob robustness sweep (standalone, locked tables untouched)

This table stops at BIP minutes + the cross-tournament ranking. For the BIP knob propagated all the way through to the HEADLINE X% (≤0.10 pp across this whole sweep), see `docs/bip_headline_sensitivity.md` / ADR-0026.

| max_live_gap | WC2018 BIP | Δ vs 54:50 | WC2022 BIP | Δ vs 58:04 | Σ\|err\| |
|---|---|---|---|---|---|
| 12s | 52:53 | -117s | 56:23 | -101s | 218s |
| 14s | 53:43 | -67s | 56:46 | -78s | 145s |
| 16s | 54:32 | -18s | 57:06 | -58s | 76s |
| 18s | 55:17 | +27s | 57:23 | -41s | 68s |
| 20s  **(chosen)** | 56:00 | +70s | 57:40 | -24s | 94s |
| 22s | 56:38 | +108s | 57:57 | -7s | 115s |
| 24s | 57:14 | +144s | 58:17 | +13s | 157s |
| 26s | 57:50 | +180s | 58:29 | +25s | 205s |
| 28s | 58:25 | +215s | 58:45 | +41s | 255s |
| 30s | 58:58 | +248s | 59:00 | +56s | 304s |
