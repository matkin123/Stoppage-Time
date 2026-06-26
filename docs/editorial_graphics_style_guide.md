# Editorial Graphics Style Guide

## Purpose

This project is intended for publication-quality journalism.

Every graphic should feel appropriate for publication in:

* Financial Times
* The Economist
* Silver Bulletin
* Our World in Data

The goal is not merely attractive charts. The goal is rapid comprehension.

A reader should understand the core message within five seconds.

---

# Audience

Assume the reader:

* Watches soccer occasionally or regularly
* Understands stoppage time
* Does not know this project
* Does not know internal methodology
* Does not know internal variable names
* Has not read accompanying text

Every chart must stand on its own.

---

# Editorial Philosophy

Priority order:

1. Story
2. Evidence
3. Methodology

A chart that is technically correct but difficult to understand is a failed chart.

A chart that makes the central insight obvious is a successful chart.

---

# Language Rules

## Use Plain English

Never use internal project terminology when a simpler alternative exists.

### Approved Translation Dictionary

| Internal Term            | Publication Term                          |
| ------------------------ | ----------------------------------------- |
| productivity             | Goals per live minute                     |
| goals per played minute  | Goals per live minute                     |
| goals per live-minute    | Goals per live minute (no hyphen)         |
| ball in play             | Live play                                 |
| BIP                      | Live play                                 |
| live minute              | a minute the ball is actually in play     |
| game state               | Match status / Score at 90 minutes        |
| calibration              | Predicted vs actual                       |
| robustness               | Alternative definitions                   |
| bucket                   | Range                                     |
| SH / 2H                  | Second half                               |
| FH / 1H                  | First half                                |
| 2H stoppage              | Second-half stoppage                      |
| 1H stop / 2H stop        | 45'+ / 90'+ (added-time ranges)           |
| group / elimination      | Group stage / Knockout                    |
| tied                     | Level                                     |
| 1-goal diff              | Within one goal                           |
| >1-goal diff             | Two or more goals apart                   |
| max_live_gap_s / the knob| Tuning threshold (seconds)                |
| omitted 2H clock         | Stoppage time not played                  |

---

# Consistent Terminology

The project should use the same language everywhere.

For expected stoppage-time models:

Choose ONE term and use it consistently.

Recommended:

**True Stoppage Time Estimate**

Examples:

* My True Stoppage Time Estimate
* Nate Silver's True Stoppage Time Estimate

Do not switch between:

* estimate
* expected
* predicted
* model output
* forecast

within the same chart.

Use one term consistently.

### The locked pair (use these exact words everywhere)

When a chart compares the modeled stoppage against what the referee actually allowed,
use this pair — and nothing else:

* **True stoppage-time estimate** — the model output (what *should* have been added).
* **Stoppage time actually played** — the measured clock (what *was* added).

Shorten to **Estimate** / **Actual** only inside a tight axis or inline label, never
mixing in "expected", "predicted", or "observed". When the comparison is against an
external benchmark, attribute it: *Nate Silver's estimate* vs *My true stoppage-time
estimate*; *Nate Silver, actual* vs *My measurement*.

Casing: sentence case in running labels ("True stoppage-time estimate"), not Title Case.

---

# Titles

Titles should communicate conclusions.

Avoid describing chart mechanics.

## Bad

* Productivity by Bucket
* Calibration Plot
* Stoppage Time Analysis
* Match State Results

## Better

* Goals arrive faster in longer matches
* Teams score more often after 90 minutes
* Actual stoppage time closely matches expectations
* Trailing teams play in longer matches

A reader should understand the takeaway from the title alone.

---

# Subtitle Rules

Every chart should have a subtitle.

Subtitle responsibilities:

* Add context
* Define unfamiliar concepts
* Explain measurement choices

Example:

Goals per live minute rise steadily as added time increases. Productivity is measured using ball-in-play minutes only.

---

# Annotation Rules

Annotations should reveal insights.

Annotations should not repeat labels.

Maximum:

* 3 annotations per chart

Good:

* Most matches finished above the prediction
* Scoring accelerates after 90 minutes
* Knockout matches show the highest scoring rate

Bad:

* Point = Match
* Blue line = Average
* X-axis = Minutes

---

# Visual Design Rules

## Background

White.

No decorative elements.

## Gridlines

Minimal.

Use only when they improve reading precision.

## Colors

Use restrained colors.

One primary highlight color.

Everything else should be neutral.

Avoid rainbow palettes.

Avoid unnecessary categorical coloring.

## Legends

Avoid whenever possible.

Prefer direct labeling.

## Labels

Labels should be human-readable.

Never show:

* snake_case
* file names
* abbreviated variables
* internal IDs

Examples:

Bad:

goals_per_live_minute

Good:

Goals per live minute

---

# Statistical Communication

Readers care about meaning.

Not methodology.

Prefer:

Goals per live minute

instead of:

Productivity

Prefer:

Predicted vs actual

instead of:

Calibration

Prefer:

Actual stoppage time

instead of:

Observed value

---

# Layout Standards

Every chart should contain:

1. Strong title
2. Informative subtitle
3. Chart area
4. Direct annotations where useful
5. Source note if applicable

Every chart should feel publication-ready when exported as a standalone image.

---

# Applied Conventions (production learnings)

These were settled while taking the first charts to publication standard. They are now
binding defaults, implemented once in `src/lib/editorial.py` (palette, fonts, title
block, footer) and imported by every figure script so the whole set reads as one family.

## The word for the core metric

The metric is **"Goals per live minute."** Always those four words, sentence case, no
hyphen. Never "productivity," "goals per played minute," or "goals per live-minute." On
first use, the subtitle defines it: *a "live minute" counts only time the ball is
actually in play.* Internally the same quantity is the Poisson rate `goals / live_min`;
that name never reaches the reader.

## Title block (text only — no decorative rule)

Every figure carries a left-aligned block, built by `editorial.titleblock()`:

1. **Title** — bold, ~17pt, states the conclusion (see Titles section). One line.
2. **Subtitle** — grey, ~10.5pt, 2–3 short lines. Tight, even leading.
3. **Footer** — small grey, two lines: the *data-scope* line then the *source* line.

There is **no accent rule, banner, or colored bar** above the title. We tried a small
red rule and removed it; the bold title alone carries the top of the chart. The block's
vertical rhythm is specified in **inches**, not figure fractions, so the title, subtitle
leading, and footer are pixel-identical across charts of different sizes.

## The footer states scope, every time

The footer's first line names the sample so the chart stands alone — e.g.
*"Data includes all 314 matches from the 2018 & 2022 World Cups, the 2020 & 2024 Euros,
the 2024 Copa América and the 2023 AFCON."* The second line is the source
(*"Source: StatsBomb open data; author's analysis."*). Charts built on a narrower slice
(e.g. a World Cup 2018 benchmark, or second-half stoppage only) say *that* in the first
line instead — never inherit the all-data line when it isn't true.

## One highlight color, everything else neutral

`HILITE` is a single red (`#D4322C`): it marks *the subject of the sentence* — added-time
bars, above-the-line matches, the central modeling assumption. Everything else is neutral
grey (`NEUTRAL` / `NEUTRAL_PT`). Do not color categories just because they are different
categories. When the point of a chart is that two groups are *the same* (group vs
knockout, level vs decided), color them the **same** neutral and let a red reference line
or annotation carry the message.

## Direct labels beat legends; reference lines need a name

Prefer labeling a series at its end, or inline along a line, over a legend box. A diagonal
identity line must be labeled in plain words on the chart ("Played = estimate"), not
explained in a legend. Any reference line (an average, a pooled rate) gets a short italic
label parked in nearby white space.

## Plain words for football concepts

"Second-half stoppage," not "2H stoppage." "Group stage / Knockout," not
"group / elimination." Score states are "Level / Within one goal / Two or more goals
apart." Added-time ranges read as "45'+" and "90'+." Never expose `snake_case`, a knob
name, or a column header to the reader.

## Annotations carry the insight, ≤3 per chart

An annotation says something the axes cannot — "Goals come nearly twice as fast in
second-half added time," "match ended too early." It is not a key. Point it at the
evidence with a thin arrow, and keep it clear of dense data (park it in white space and
arc the arrow in).

# Quality Check

Before finalizing any chart, ask:

1. Can a casual soccer fan understand this immediately?
2. Is the title communicating the insight?
3. Have all technical labels been translated?
4. Is the chart understandable without project context?
5. Would this feel at home in the Financial Times or The Economist?

If the answer to any question is no, revise.
