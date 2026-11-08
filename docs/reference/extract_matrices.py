"""Extract bullet capability matrices (Tables 68-70) from the Alpha protocol PDF.

One-off tool, kept for reproducibility. Run from the repo root:

    uv run --no-project --with pymupdf python docs/reference/extract_matrices.py \
        docs/reference/M-Protocol.pdf src/alpha_led_sign/capability-matrices.json \
        docs/reference/capability-matrices.md
"""
import json, sys, pathlib, pymupdf

def spans(page):
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip()
                if t:
                    yield t, s["bbox"], l["dir"], s["size"]

def extract(page, title):
    ss = list(spans(page))
    bullets = [(b, sz) for t, b, d, sz in ss if t == "●"]
    top = min(b[1] for b, _ in bullets) - 4
    bottom = max(b[3] for b, _ in bullets) + 4
    allrot = [(t, b) for t, b, d, _ in ss if round(d[1]) == -1 and b[3] < top]
    marks = [(t, b) for t, b in allrot if t.isdigit()]
    rot = [(t, b) for t, b in allrot if not t.isdigit()]
    def mark(b):  # header footnote: digit just above (rotated text reads bottom-up) the label
        m = [t for t, mb in marks if abs(mb[0] - b[0]) < 6 and -1 <= b[1] - mb[3] < 6]
        return f" [{m[0]}]" if m else ""
    # group headers: rotated labels with another rotated label beneath them
    groups, leaves = [], []
    for t, b in rot:
        cx = (b[0] + b[2]) / 2
        below = [r for r in rot if r[1][1] > b[3] and abs((r[1][0] + r[1][2]) / 2 - cx) < 16]
        (groups if below else leaves).append((t, b))
    cols = []
    for t, b in leaves:
        cx = (b[0] + b[2]) / 2
        parent = [g for g, gb in groups if gb[3] < b[1] and abs((gb[0] + gb[2]) / 2 - cx) < 16]
        cols.append(((f"{parent[0]}: {t}" if parent else t) + mark(b), cx))
    cols.sort(key=lambda c: c[1])
    # row labels: horizontal, left of the first column, within the body
    first_x = cols[0][1] - 8
    rows = []
    for t, b, d, sz in ss:
        if round(d[0]) == 1 and b[2] <= first_x and top <= b[1] <= bottom and sz >= 7.5:
            cy = (b[1] + b[3]) / 2
            if rows and abs(rows[-1][1] - cy) < 3:
                rows[-1] = (rows[-1][0] + t, cy)
            else:
                rows.append((t, cy))
    rows = [(r.rstrip(":").strip(), y) for r, y in rows if r.rstrip(":").strip()]
    grid = {r: {} for r, _ in rows}
    for b, _ in bullets:
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        row = min(rows, key=lambda r: abs(r[1] - cy))
        col = min(cols, key=lambda c: abs(c[1] - cx))
        assert abs(row[1] - cy) < 6 and abs(col[1] - cx) < 9, (row, col, b)
        # footnote: small digit immediately right of the bullet
        note = next((t for t, sb, d, sz in ss if sz < 7 and t.isdigit() and -1 <= sb[0] - b[2] < 3 and abs(sb[1] - b[1]) < 5), None)
        grid[row[0]][col[0]] = note or True
    return {"title": title, "columns": [c for c, _ in cols], "rows": grid}

doc = pymupdf.open(sys.argv[1])
out = [extract(doc[p - 1], t) for p, t in [(91, "Table 68: Modes available on signs"),
                                           (92, "Table 69: Fonts and colors available on signs"),
                                           (93, "Table 70: Display options available on signs")]]
json.dump(out, open(sys.argv[2], "w"), indent=1)
for tbl in out:
    print(tbl["title"]); print(" cols:", tbl["columns"]); print(" rows:", list(tbl["rows"]))
    print(" 4000:", tbl["rows"].get("4000 Series4") or tbl["rows"].get("4000 Series"))

notes = {
 68: ["1 If Slide is selected on a 220C or 420C, Cycle Color is used instead; the same applies to Spray on the 420C only.",
      "8 7-high character set only."],
 69: ["1 Models ending in C (e.g. 4120C) have color; models ending in R display red only.",
      "8 RoadStar and StreetSmart cannot display color, but can display up to 256 shades / greyscale."],
 70: ["1 A graphic, gif, or flick must fit the sign's resolution (4120C: 120 columns x 16 rows).",
      "8 BetaBrite can display the date, but it is not real-time and will not change."],
}
common = ["2 200 Series includes 215R and 215C.", "3 300 Series includes 320C and 330C.",
          "4 4000 Series includes 4080C, 4120C, 4120R, 4160C, 4160R, 4200C, 4200R, 4240C, 4240R (C = tricolor, R = red).",
          "5 7000 Series includes 7080C, 7120C, 7160C, 7200C.",
          "6 Displays time updates from messaging software only; cannot display text or graphics.",
          "7 AlphaEclipse 3600 has RGB LEDs."]
md = ["# Alpha sign capability matrices", "",
      "Extracted from *Alpha Sign Communications Protocol* (9708-8061F, March 10, 2006), Appendix I, pages 91-93 ([M-Protocol.pdf](M-Protocol.pdf)).",
      "Cells were read from glyph positions in the PDF and checked against the rendered pages.",
      "",
      "Legend: `Y` = supported, `Yn` = supported with footnote *n*, blank = not supported. Footnote numbers in column headers refer to the same notes.",
      "Row footnote numbers (2-7) from the original are dropped from the row names; see the shared notes at the end.", ""]
for (num, tbl) in zip((68, 69, 70), out):
    cols = tbl["columns"]
    md += [f"## {tbl['title']}", "", "| Sign | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for row, cells in tbl["rows"].items():
        name = row
        def cell(c):
            v = cells.get(c)
            return "" if v is None else ("Y" if v is True else f"Y{v}")
        md.append(f"| {name} | " + " | ".join(cell(c) for c in cols) + " |")
    md += ["", "Notes:", ""] + [f"- {n}" for n in notes[num]] + [""]
md += ["## Shared row notes", ""] + [f"- {n}" for n in common] + [""]
pathlib.Path(sys.argv[3]).write_text("\n".join(md))
