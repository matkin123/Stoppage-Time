# Method 2 (same-half live share + same-half gross-up z) -- ANALYSIS, NOT A LOCK

Standalone test of the user's preferred fix for the s08 gross-up live-share / z asymmetry (ADR-0027). Omitted added-time minutes are assumed to look like the average SAME-HALF minute (that half's regular play + played stoppage) for BOTH the live share and the gross-up z. READS production parquet; no locked artifact touched. Central spec `silent_marked|overall|pooled_all|hl=4.0|on`, gross-up ON, decay h=4.0.

## Headline X% (deterministic central point)

| window | locked (ADR-0025) | Method 1 (ADR-0027) | **Method 2** |
|---|---|---|---|
| scoreline 1H+2H | 23.6% | ~23.4% | **25.31%** |
| scoreline 2H_only | 16.0% | -- | **17.39%** |
| outcome-flip 1H+2H | 12.1% | -- | **13.18%** |
| outcome-flip 2H_only | -- | -- | **9.09%** |

Gross-up rail band (ADR-0024, h=4): **[21.1%, 24.2%]** (off .. geometric). Method 2 scoreline 1H+2H = **25.31%** -> **OUTSIDE** the band.

## Spain-England (Euro 2024 final), state@90 = lead_by_1

| quantity | locked central | Method 1 | **Method 2** |
|---|---|---|---|
| omitted clock (min) | 11.59 | (same) | 11.59 |
| omitted LIVE (min) | 3.95 | -- | 7.70 |
| P scoreline | 19.6% | 17.8% | **34.64%** |
| P flip | 10.3% | 9.3% | **19.15%** |
| 2H live share used | 0.258 (lsw) | -- | 0.528 (ls_half) |
| 2H z used | 0.382 (pooled) | 0.008 (window) | 0.361 (z_half) |

## Channel decomposition (1H+2H scoreline X%)

- central -> Method 2: **+1.69 pp** (23.61% -> 25.31%).
- **A: live-share swap** (ls_half, pooled z) = 24.57% (**+0.96 pp**) -- this is the BROKEN-CANCELLATION channel.
- **B: z swap** (lsw, z_half) = 24.33% (**+0.72 pp**).
- interaction = +0.01 pp. BOTH channels push the headline UP and are comparable in size (live-share +0.96 pp, z_half +0.72 pp).

## Diagnostics

- pooled-mean live share -- **1H**: ls_half 0.577 vs lsw 0.567; **2H**: ls_half 0.533 vs lsw 0.505.
- pooled-mean z_half -- **1H** 0.292, **2H** 0.434, **overall** 0.363 vs pooled scalar z=0.382.
- corr(ls_half, z_half) over all (match,half) = **-0.389**.
- lambda rates UNCHANGED (pooled): lam1=0.0478, obs2=0.0816, floor2=0.0427.

**Cancellation caveat.** The locked headline is robust partly because live share scales BOTH omitted-live AND lambda-exposure (mu ~= G*omitted/total, ADR-0026). Method 2 changes the omitted-live live share but NOT the lambda-exposure live share (still stoppage-window live-minutes in build_lambda_cells), so it deliberately breaks that cancellation.
