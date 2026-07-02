"""Shared editorial chart styling (publication standard).

Single source of the title block, palette, fonts, and standard footer used by every
publication figure, so the whole set renders as one coherent family. The principles
these encode are documented in docs/editorial_graphics_style_guide.md.

Import, then wrap drawing in `with plt.rc_context(editorial.RC):` and finish with
`editorial.titleblock(fig, title, [subtitle lines], source)`.
"""
from __future__ import annotations

import matplotlib.pyplot as plt

# ---- palette: ONE highlight, everything else neutral --------------------------
HILITE = "#D4322C"      # the single highlight colour (the subject / the story)
HILITE_SOFT = "#E8A29F"  # tint of the highlight, for secondary highlighted marks
NEUTRAL = "#B7BCC2"     # recessive grey for context bars
NEUTRAL_PT = "#A6ABB2"  # grey for context points
SLATE = "#5B6E8C"       # muted blue, for a 2nd neutral series (e.g. PRE)
INK = "#222222"         # title + primary text
SUBINK = "#5A5F66"      # subtitle + axis labels
FAINT = "#8A8F96"       # footer / source note
GRID = "#E6E8EA"        # gridlines
REF = "#6B7178"         # reference lines (averages, identity)

RC = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "axes.edgecolor": "#3C4043",
    "axes.linewidth": 0.8,
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": "#3C4043",
    "ytick.color": "#3C4043",
    "svg.fonttype": "none",
}

# Standard footer for the all-data figures: states the match count + the six
# tournaments, then the source line. Charts on a narrower slice pass their own.
FOOTER = ("Data includes all 314 matches from the 2018 & 2022 World Cups, the 2020 & "
          "2024 Euros, the 2024 Copa América and the 2023 AFCON.\nSource: StatsBomb "
          "open data; author’s analysis.")


def _renderer(fig):
    """A usable Agg renderer for measuring text extents before the figure is drawn."""
    try:
        return fig.canvas.get_renderer()
    except AttributeError:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        return FigureCanvasAgg(fig).get_renderer()


def _wrap_to_px(fig, text, max_px, fontsize):
    """Greedily wrap `text` so each rendered line is no wider than `max_px` pixels."""
    r = _renderer(fig)
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        probe = fig.text(0, 0, trial, fontsize=fontsize)
        wpx = probe.get_window_extent(renderer=r).width
        probe.remove()
        if cur and wpx > max_px:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def titleblock(fig, title, subtitle, source, left_in=0.46, title_size=17,
               content_gap_in=0.40, subtitle_width_in=None):
    """Left-aligned Economist/FT-style title band (no decorative rule).

    Vertical rhythm is set in INCHES (converted to figure fraction via the figure
    height) so the title, subtitle line spacing, and footer look identical across
    figures of different sizes. `left_in` is the left margin in inches: raise it to
    add whitespace on the sides without resizing the plotted content.

    `subtitle` may be a list of pre-broken lines OR a single string. A string is
    wrapped so the subtitle spans the SAME width as the title (or `subtitle_width_in`
    inches if given), instead of breaking early. `source` may contain a newline (top
    line is the data-scope note, second line the source).

    Returns the figure-fraction y of the top of the chart content — the subtitle's
    bottom edge plus `content_gap_in` inches — so callers can seat their axes a
    standard distance below the subtitle (keeps that whitespace identical across
    figures of different heights).
    """
    W, H = fig.get_size_inches()
    x = left_in / W

    def fy(inches_from_top):
        return 1.0 - inches_from_top / H

    title_artist = fig.text(x, fy(0.44), title, ha="left", va="top",
                            fontsize=title_size, fontweight="bold", color=INK)

    if isinstance(subtitle, str):
        if subtitle_width_in is not None:
            max_px = subtitle_width_in * fig.dpi
        else:
            max_px = title_artist.get_window_extent(renderer=_renderer(fig)).width
        subtitle = _wrap_to_px(fig, subtitle, max_px, 10.5)

    yi = 0.80
    sub_line_h = 10.5 / 72.0
    subtitle_bottom_in = yi + sub_line_h
    for line in subtitle:
        fig.text(x, fy(yi), line, ha="left", va="top", fontsize=10.5, color=SUBINK)
        subtitle_bottom_in = yi + sub_line_h
        yi += 0.185
    slines = source.split("\n")
    for i, line in enumerate(slines):
        y_in = 0.30 + 0.135 * (len(slines) - 1 - i)  # first line sits on top
        fig.text(x, y_in / H, line, ha="left", va="bottom", fontsize=8, color=FAINT)

    return fy(subtitle_bottom_in + content_gap_in)


def despine(ax, keep=("left", "bottom")):
    """Drop chart junk: hide unkept spines, zero out tick marks, send grid behind."""
    for sp in ("top", "right", "left", "bottom"):
        ax.spines[sp].set_visible(sp in keep)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)


def plain_table_figure(*, columns, cell_text, col_widths, aligns, savepath,
                       figsize=(11.0, 3.0), fontsize=11, bold_cells=(), bold_rows=(),
                       band=(0.01, 0.04, 0.98, 0.92), dpi=200,
                       title=None, source=None, left_in=0.46, title_size=17):
    """Render a BARE black-and-white table — header + data rows, light rules, nothing else.

    NO colour of any kind (the article prose supplies the context; see the Substack tables).
    Header is bold ink with a rule above and below; body rows carry a faint separator and a
    closing rule under the last row. `bold_cells` (set of (body_row, col), 0-based among DATA
    rows) and `bold_rows` (set of body_row) bold text for emphasis — emphasis stays
    monochrome. `aligns` is one of 'left'/'center'/'right' per column.

    By default there is no title, subtitle, or source footer. Optionally pass `title` and/or
    `source` to add the family's left-aligned title and a faint source footer (still no
    subtitle, still monochrome); when either is given the table band is recomputed in inches
    so the gaps above/below stay consistent across figure sizes. Returns the saved path.
    """
    bold_cells = set(bold_cells)
    bold_rows = set(bold_rows)
    nbody = len(cell_text)

    with plt.rc_context(RC):
        fig = plt.figure(figsize=figsize)
        if title is not None or source is not None:
            W, H = figsize
            x = left_in / W
            top_in = 0.18  # table top edge, inches from the figure top
            if title is not None:
                fig.text(x, 1.0 - 0.44 / H, title, ha="left", va="top",
                         fontsize=title_size, fontweight="bold", color=INK)
                top_in = 0.44 + title_size / 72.0 + 0.30  # title height + gap below
            bottom_in = 0.12  # table bottom edge, inches from the figure bottom
            if source is not None:
                slines = source.split("\n")
                for i, line in enumerate(slines):
                    y_in = 0.30 + 0.135 * (len(slines) - 1 - i)  # first line on top
                    fig.text(x, y_in / H, line, ha="left", va="bottom",
                             fontsize=8, color=FAINT)
                bottom_in = 0.30 + 0.135 * (len(slines) - 1) + 8 / 72.0 + 0.26
            band = (x, bottom_in / H, 1.0 - 2 * left_in / W,
                    1.0 - (top_in + bottom_in) / H)
        ax = fig.add_axes(list(band))
        ax.axis("off")
        t = ax.table(cellText=cell_text, colLabels=columns, colWidths=col_widths,
                     bbox=[0, 0, 1, 1])
        t.auto_set_font_size(False)
        t.set_fontsize(fontsize)
        for (row, col), cell in t.get_celld().items():
            cell.set_edgecolor("none")
            cell.PAD = 0.05
            ha = aligns[col]
            if row == 0:  # header: bold ink, rule above + below
                cell.visible_edges = "TB"
                cell.set_edgecolor(INK)
                cell.set_linewidth(1.2)
                cell.set_text_props(fontweight="bold", ha=ha, color=INK)
            else:  # body: faint separators; bold the last row's closing edge in ink
                br = row - 1
                last = br == nbody - 1
                cell.visible_edges = "B"
                cell.set_edgecolor(INK if last else GRID)
                cell.set_linewidth(1.2 if last else 0.7)
                weight = "bold" if (br in bold_rows or (br, col) in bold_cells) else "normal"
                cell.set_text_props(ha=ha, color=INK, fontweight=weight)

        fig.savefig(savepath, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
    print(f"  wrote {savepath}")
    return savepath


def table_figure(*, title, subtitle, source, columns, cell_text, col_widths,
                 aligns, savepath, figsize=(11.0, 4.8),
                 band=(0.04, 0.17, 0.92, 0.44), left_in=0.42, fontsize=11,
                 hilite_cells=(), bold_cells=(), hilite_header_cols=(),
                 dim_cells=(), dpi=130):
    """Render a publication-standard editorial TABLE as a standalone figure.

    Mirrors the rest of the family: white ground, the left-aligned title block, a
    scope+source footer, ONE highlight colour. The table itself is rules-light — a
    bold ink underline beneath the header, faint separators between body rows, no
    vertical edges. Cell coordinates for highlighting are (body_row, col) with
    body_row 0-based among DATA rows (the header is addressed via hilite_header_cols).

    `hilite_cells` paints text in HILITE (the subject of the table); `bold_cells`
    bolds it; `dim_cells` greys it (e.g. an em-dash placeholder). `aligns` is one of
    'left'/'center'/'right' per column. Returns the saved path.
    """
    hilite_cells = set(hilite_cells)
    bold_cells = set(bold_cells)
    dim_cells = set(dim_cells)
    hilite_header_cols = set(hilite_header_cols)
    ncol = len(columns)

    with plt.rc_context(RC):
        fig = plt.figure(figsize=figsize)
        ax = fig.add_axes(list(band))
        ax.axis("off")
        t = ax.table(cellText=cell_text, colLabels=columns, colWidths=col_widths,
                     bbox=[0, 0, 1, 1])
        t.auto_set_font_size(False)
        t.set_fontsize(fontsize)
        for (row, col), cell in t.get_celld().items():
            cell.set_edgecolor("none")
            cell.PAD = 0.045
            ha = aligns[col]
            if row == 0:  # header: bold ink, bottom rule, optional red columns
                cell.visible_edges = "B"
                cell.set_edgecolor(INK)
                cell.set_linewidth(1.2)
                cell.set_text_props(fontweight="bold", ha=ha,
                                    color=HILITE if col in hilite_header_cols else INK)
            else:  # body: faint row separator; per-cell highlight / bold / dim
                br = row - 1
                cell.visible_edges = "B"
                cell.set_edgecolor(GRID)
                cell.set_linewidth(0.8)
                color = INK
                if (br, col) in hilite_cells:
                    color = HILITE
                elif (br, col) in dim_cells:
                    color = FAINT
                weight = "bold" if ((br, col) in bold_cells
                                    or (br, col) in hilite_cells) else "normal"
                cell.set_text_props(ha=ha, color=color, fontweight=weight)

        titleblock(fig, title, subtitle, source, left_in=left_in)
        fig.savefig(savepath, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
    print(f"  wrote {savepath}")
    return savepath
