# -*- coding: utf-8 -*-
from pathlib import Path
import sys
import html
from datetime import datetime

# ============================================================
# CONFIG (EDIT HERE ONLY)
# ============================================================

# Single template used for all languages
TEMPLATE_FILE = Path("reaper_769.txt")

# Language sources: key = language code (folder name), value = source file
LANGUAGES = {
     "ARABIC": Path("ARABIC_769.txt"),
     "BENGALI_R769": Path("BENGALI_R769.txt"),
     "BULGARIAN": Path("BULGARIAN_769.txt"),
     "FRENCH_R769": Path("FRENCH_R769.txt"),
     "Hindi": Path("Hindi_R769.txt"),
     "INDONESIAN": Path("INDONESIAN_R769.txt"),
     "ITALIAN": Path("ITALIAN_R769.txt"),
     "JAPANESE": Path("JAPANESE_R769.txt"),
     "KOREAN": Path("KOREAN_R769.txt"),
     "PORTUGUESE": Path("PORTUGUESE_R769.txt"),
     "PUNJABI": Path("PUNJABI_R769.txt"),
     "SIMPLIFIED_CHINESE": Path("SIMPLIFIED_CHINESE_R769.txt"),
     "SPANISH": Path("SPANISH_R769.txt"),
     "SWAHILI": Path("SWAHILI_R769.txt"),
     "Thai": Path("Thai_R769.txt"),
     "TRADITIONAL_CHINESE": Path("TRADITIONAL_CHINESE_R769.txt"),
     "TURKISH": Path("TURKISH_R769.txt"),
     "VIETNAMESE": Path("VIETNAMESE_R769.txt"),
}

# Base output directory (reports + per-language folders)
BASE_OUT_DIR = Path("output")   # use Path(".") for current folder

# Global dashboard output
DASHBOARD_HTML = BASE_OUT_DIR / "LangPack_DASHBOARD.html"

# Versioning: add a suffix based on template file name (e.g. _reaper_769)
INCLUDE_TEMPLATE_TAG_IN_FILENAMES = True

# Thresholds for dashboard alerts
COVERAGE_ALERT_THRESHOLD = 98.0   # percent; highlight if coverage below this
ADDED_ALERT_THRESHOLD = 50        # highlight if added lines >= this
REMOVED_ALERT_THRESHOLD = 50      # highlight if removed lines >= this

# If True: remove leading spaces/tabs AFTER '=' on REAPER key lines only (16-hex keys)
STRIP_LEADING_SPACES_AFTER_EQUAL_ON_KEY_LINES = True

# Credit/license line shown in the TOP header card of each report (HTML allowed)
HTML_HEADER_CREDIT = (
    "REAPER Language Tool Updater - by Acrosonus Mastering Studio<br>"
    "Copyright &copy; 2024-2026 Acrosonus Mastering Studio<br>"
    "Licensed under Creative Commons <b>CC BY-NC-SA 4.0</b>."
)

# ============================================================
# INTERNAL HELPERS
# ============================================================

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def sanitize_tag(s):
    # Keep only safe filename characters
    out = []
    for ch in s:
        if ch.isalnum() or ch in ("_", "-", "."):
            out.append(ch)
        else:
            out.append("_")
    return "".join(out)

def template_tag():
    # Build version tag from template filename stem, e.g. "reaper_769"
    stem = TEMPLATE_FILE.stem
    tag = sanitize_tag(stem)
    return tag if tag else "template"

def maybe_tag_suffix():
    return "_" + template_tag() if INCLUDE_TEMPLATE_TAG_IN_FILENAMES else ""

# ============================================================
# UTILITIES (no regex), REAPER-safe
# ============================================================

def rstrip_eol_and_trailing_spaces(s):
    return s.rstrip("\n").rstrip()

def is_section_line(line):
    p = line.lstrip(" \t")
    if not p.startswith("["):
        return False
    rb = p.find("]")
    if rb <= 1:
        return False
    if "=" in p:
        return False
    return True

def section_name_from_line(line):
    p = line.lstrip(" \t")
    return p[1:p.find("]")].strip()

def raw_key_from_line(line):
    if "=" not in line:
        return None
    return line.split("=", 1)[0].strip()

def normalize_key_from_line(line):
    rk = raw_key_from_line(line)
    if not rk:
        return None
    return rk.lstrip(";^").strip()

def is_reaper_hex_key(base_key):
    if not base_key or len(base_key) != 16:
        return False
    for c in base_key:
        if c not in "0123456789abcdefABCDEF":
            return False
    return True

def normalize_kv_spacing_if_key_line(line):
    """
    Remove leading spaces/tabs after '=' ONLY for REAPER key lines (16 hex keys).
    Keeps everything else untouched.
    """
    if not STRIP_LEADING_SPACES_AFTER_EQUAL_ON_KEY_LINES:
        return line
    if "=" not in line:
        return line

    left, right = line.split("=", 1)
    base = left.strip().lstrip(";^").strip()
    if not is_reaper_hex_key(base):
        return line

    right2 = right.lstrip(" \t")
    return left + "=" + right2

# ============================================================
# PARSE LANGUAGE FILE
# source_by_base[section][base_key] = { raw_key: full_line }
# ============================================================

def parse_language_file(source_path):
    source_name_line = None
    current_section = None
    source_by_base = {}

    with source_path.open("r", encoding="utf-8-sig") as f:
        for raw in f:
            line = rstrip_eol_and_trailing_spaces(raw)

            if line.startswith("#NAME:") and source_name_line is None:
                source_name_line = line

            if is_section_line(line):
                current_section = section_name_from_line(line)
                source_by_base.setdefault(current_section, {})
                continue

            if not current_section:
                continue
            if not line:
                continue

            p = line.lstrip(" \t")
            if p.startswith("#") and not p.startswith("#NAME:"):
                continue

            rk = raw_key_from_line(line)
            if not rk:
                continue

            base = rk.lstrip(";^").strip()
            source_by_base.setdefault(current_section, {}).setdefault(base, {})[rk] = line

    return source_name_line, source_by_base

# ============================================================
# LIKE COCKOS GotKey(): base, ;base, ;^base
# ============================================================

def find_best_source_line(source_by_base, section, base_key):
    sec = source_by_base.get(section)
    if not sec:
        return None

    variants = sec.get(base_key)
    if not variants:
        return None

    if base_key in variants:
        return variants[base_key]
    semi = ";" + base_key
    if semi in variants:
        return variants[semi]
    semihat = ";^" + base_key
    if semihat in variants:
        return variants[semihat]

    return next(iter(variants.values()))

# ============================================================
# HTML REPORT (ENGLISH)
# ============================================================

def build_html_report(lang_label, template_path, source_path, out_path, added_lines, removed_lines, stats, code):
    tnow = now_str()

    total_tmpl = sum(s["total_template_keys"] for s in stats.values())
    total_translated = sum(s["translated"] for s in stats.values())
    total_added = sum(s["added"] for s in stats.values())
    total_removed = sum(s["removed"] for s in stats.values())
    coverage = (total_translated / total_tmpl * 100.0) if total_tmpl else 100.0

    def svg_bar(translated, added, removed, width=420, height=14):
        total = translated + added + removed
        if total <= 0:
            total = 1
        scale = width / total
        w_t = translated * scale
        w_a = added * scale
        w_r = removed * scale
        x_a = w_t
        x_r = w_t + w_a
        return f"""
<svg width="{width}" height="{height}">
  <rect x="0" y="0" width="{w_t:.2f}" height="{height}" fill="#4caf50"></rect>
  <rect x="{x_a:.2f}" y="0" width="{w_a:.2f}" height="{height}" fill="#81c784"></rect>
  <rect x="{x_r:.2f}" y="0" width="{w_r:.2f}" height="{height}" fill="#e57373"></rect>
</svg>
"""

    added_by_sec = {}
    for sec, ln, line in added_lines:
        added_by_sec.setdefault(sec, []).append((ln, line))

    removed_by_sec = {}
    for sec, line in removed_lines:
        removed_by_sec.setdefault(sec, []).append(line)

    tag = template_tag()
    parts = []
    parts.append(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>REAPER LangPack - Merge Report ({html.escape(lang_label)})</title>
<style>
body {{ font-family: Consolas, monospace; background:#111; color:#eee; margin:20px; }}
h1,h2,h3 {{ font-family: Segoe UI, Arial, sans-serif; }}
.card {{ background:#1a1a1a; border:1px solid #333; border-radius:10px; padding:14px 16px; margin:12px 0; }}
.kpi {{ display:flex; flex-wrap:wrap; gap:12px; }}
.kpi .item {{ background:#151515; border:1px solid #2a2a2a; border-radius:10px; padding:10px 12px; min-width:200px; }}
small.muted {{ color:#aaa; }}
.legend span {{ display:inline-block; margin-right:12px; }}
.dot {{ display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:6px; vertical-align:middle; }}
.dot.t {{ background:#4caf50; }} .dot.a {{ background:#81c784; }} .dot.r {{ background:#e57373; }}
table {{ border-collapse:collapse; width:100%; }}
th,td {{ border-bottom:1px solid #2b2b2b; padding:6px 8px; text-align:left; }}
tr:hover {{ background:#171717; }}
details {{ margin:10px 0; }}
pre {{ white-space:pre-wrap; word-break:break-word; margin:0; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:999px; border:1px solid #444; background:#121212; }}
.badge.add {{ border-color:#2e7d32; }}
.badge.rem {{ border-color:#c62828; }}
.badge.tr {{ border-color:#1565c0; }}
hr {{ border:0; border-top:1px solid #333; margin:16px 0; }}
.credit {{ opacity:0.92; font-size:12px; line-height:1.35; }}
</style>
</head>
<body>
<h1>REAPER LangPack - Merge Report ({html.escape(lang_label)})</h1>

<div class="card">
  <div><small class="muted">Generated: {tnow}</small></div>
  <div><small class="muted">Template: {html.escape(str(template_path))} (tag: {html.escape(tag)})</small></div>
  <div><small class="muted">Language file: {html.escape(str(source_path))}</small></div>
  <div><small class="muted">Output: {html.escape(str(out_path))}</small></div>
  <div><small class="muted">Language code: {html.escape(code)}</small></div>
  <div style="margin-top:8px;"><small class="muted credit">{HTML_HEADER_CREDIT}</small></div>
</div>

<div class="card">
  <h2>Global summary</h2>
  <div class="legend">
    <span><span class="dot t"></span>Translated</span>
    <span><span class="dot a"></span>Added (template missing in language)</span>
    <span><span class="dot r"></span>Removed (language missing in template)</span>
  </div>
  <div class="kpi">
    <div class="item"><div class="badge tr">Translated</div><div style="font-size:22px">{total_translated}</div></div>
    <div class="item"><div class="badge add">Added</div><div style="font-size:22px">{total_added}</div></div>
    <div class="item"><div class="badge rem">Removed</div><div style="font-size:22px">{total_removed}</div></div>
    <div class="item"><div class="badge">Total template keys</div><div style="font-size:22px">{total_tmpl}</div></div>
    <div class="item"><div class="badge">Coverage</div><div style="font-size:22px">{coverage:.1f}%</div></div>
  </div>
</div>

<div class="card">
  <h2>Per-section chart</h2>
  <table>
    <tr><th>Section</th><th>Bar</th><th>Details</th></tr>
""")

    for sec in sorted(stats.keys()):
        s = stats[sec]
        parts.append(
            f"<tr><td><b>[{html.escape(sec)}]</b><br>"
            f"<small class='muted'>Template keys: {s['total_template_keys']}</small></td>"
            f"<td>{svg_bar(s['translated'], s['added'], s['removed'])}</td>"
            f"<td>Translated: {s['translated']} | Added: {s['added']} | Removed: {s['removed']}</td></tr>"
        )

    parts.append("""  </table>
</div>

<div class="card">
  <h2>Details (Added / Removed lines)</h2>
  <p><small class="muted">Added lines are kept from the template (missing translations). Removed lines exist in language but not in template (including ; and ;^).</small></p>
  <hr>
""")

    for sec in sorted(stats.keys()):
        adds = added_by_sec.get(sec, [])
        rems = removed_by_sec.get(sec, [])

        parts.append(
            f"<details><summary><b>[{html.escape(sec)}]</b> - "
            f"<span class='badge tr'>Translated: {stats[sec]['translated']}</span> "
            f"<span class='badge add'>Added: {len(adds)}</span> "
            f"<span class='badge rem'>Removed: {len(rems)}</span></summary>"
        )

        if adds:
            parts.append("<h3>Added (to translate)</h3><ul>")
            for ln, line in sorted(adds, key=lambda x: x[0]):
                parts.append(f"<li><span class='badge add'>line {ln}</span> <pre>{html.escape(line)}</pre></li>")
            parts.append("</ul>")
        else:
            parts.append("<p><small class='muted'>No added lines.</small></p>")

        if rems:
            parts.append("<h3>Removed</h3><ul>")
            for line in rems:
                parts.append(f"<li><span class='badge rem'>removed</span> <pre>{html.escape(line)}</pre></li>")
            parts.append("</ul>")
        else:
            parts.append("<p><small class='muted'>No removed lines.</small></p>")

        parts.append("</details>")

    parts.append("</div></body></html>")
    return "\n".join(parts)

# ============================================================
# MERGE ONE LANGUAGE (outputs into a per-language folder)
# ============================================================

def merge_one(template_path, source_path, lang_out_dir, code):
    lang_out_dir.mkdir(parents=True, exist_ok=True)

    suffix = maybe_tag_suffix()

    out_path    = lang_out_dir / f"LangPack_{code}_SYNCED{suffix}.txt"
    added_log   = lang_out_dir / f"LangPack_{code}_ADDED{suffix}.txt"
    removed_log = lang_out_dir / f"LangPack_{code}_REMOVED{suffix}.txt"
    report_path = lang_out_dir / f"LangPack_{code}_REPORT{suffix}.html"

    source_name_line, source_by_base = parse_language_file(source_path)

    output_lines = []
    added_lines = []
    template_basekeys = set()
    template_count_by_section = {}

    current_section = None
    out_line_no = 0

    with template_path.open("r", encoding="utf-8-sig") as f:
        for raw in f:
            line = rstrip_eol_and_trailing_spaces(raw)

            if line.startswith("#NAME:") and source_name_line:
                output_lines.append(source_name_line)
                out_line_no += 1
                continue

            if is_section_line(line):
                current_section = section_name_from_line(line)
                output_lines.append(line)
                out_line_no += 1
                continue

            base = normalize_key_from_line(line)
            if base and current_section:
                template_basekeys.add((current_section, base))
                template_count_by_section[current_section] = template_count_by_section.get(current_section, 0) + 1

                repl = find_best_source_line(source_by_base, current_section, base)
                if repl is not None:
                    output_lines.append(normalize_kv_spacing_if_key_line(repl))
                else:
                    kept = normalize_kv_spacing_if_key_line(line)
                    output_lines.append(kept)
                    added_lines.append((current_section, out_line_no + 1, kept))

                out_line_no += 1
                continue

            output_lines.append(line)
            out_line_no += 1

    removed_lines = []
    for sec, base_map in source_by_base.items():
        for base_key, variants in base_map.items():
            if (sec, base_key) not in template_basekeys:
                for full_line in variants.values():
                    removed_lines.append((sec, normalize_kv_spacing_if_key_line(full_line)))

    stats = {}
    all_sections = set(template_count_by_section.keys()) | set(source_by_base.keys())
    for sec in all_sections:
        stats[sec] = {"total_template_keys": template_count_by_section.get(sec, 0),
                      "added": 0, "removed": 0, "translated": 0}

    for sec, _, _ in added_lines:
        stats.setdefault(sec, {"total_template_keys": 0, "added": 0, "removed": 0, "translated": 0})
        stats[sec]["added"] += 1

    for sec in stats:
        t = stats[sec]["total_template_keys"]
        a = stats[sec]["added"]
        stats[sec]["translated"] = max(t - a, 0)

    for sec, _ in removed_lines:
        stats.setdefault(sec, {"total_template_keys": 0, "added": 0, "removed": 0, "translated": 0})
        stats[sec]["removed"] += 1

    # Write outputs
    with out_path.open("w", encoding="utf-8-sig", newline="\n") as f:
        for l in output_lines:
            f.write(l + "\n")

    with added_log.open("w", encoding="utf-8") as f:
        for sec, ln, l in added_lines:
            f.write(f"[{sec}] | line {ln} | {l}\n")

    with removed_log.open("w", encoding="utf-8") as f:
        for sec, l in removed_lines:
            f.write(f"[{sec}] | {l}\n")

    lang_label = (source_name_line[6:].strip()
                  if source_name_line and source_name_line.startswith("#NAME:")
                  else source_path.name)

    html_content = build_html_report(lang_label, template_path, source_path, out_path, added_lines, removed_lines, stats, code)
    with report_path.open("w", encoding="utf-8") as f:
        f.write(html_content)

    total_tmpl = sum(s["total_template_keys"] for s in stats.values())
    total_translated = sum(s["translated"] for s in stats.values())
    total_added = sum(s["added"] for s in stats.values())
    total_removed = sum(s["removed"] for s in stats.values())
    coverage = (total_translated / total_tmpl * 100.0) if total_tmpl else 100.0

    added_ratio = (total_added / total_tmpl * 100.0) if total_tmpl else 0.0
    removed_ratio = (total_removed / total_tmpl * 100.0) if total_tmpl else 0.0

    return {
        "code": code,
        "lang_label": lang_label,
        "template_keys": total_tmpl,
        "translated": total_translated,
        "added": total_added,
        "removed": total_removed,
        "coverage": coverage,
        "added_ratio": added_ratio,
        "removed_ratio": removed_ratio,
        "report_rel": f"{code}/LangPack_{code}_REPORT{suffix}.html",
        "out_rel": f"{code}/LangPack_{code}_SYNCED{suffix}.txt",
    }

# ============================================================
# DASHBOARD (global, enriched)
# ============================================================

def status_badges(r):
    alerts = []
    if r["coverage"] < COVERAGE_ALERT_THRESHOLD:
        alerts.append("LOW_COVERAGE")
    if r["added"] >= ADDED_ALERT_THRESHOLD:
        alerts.append("MANY_ADDED")
    if r["removed"] >= REMOVED_ALERT_THRESHOLD:
        alerts.append("MANY_REMOVED")
    return alerts

def build_dashboard(results):
    tnow = now_str()
    tag = template_tag()

    # Sort: lowest coverage first, then highest added, then highest removed
    results_sorted = sorted(
        results,
        key=lambda r: (r["coverage"], -r["added"], -r["removed"], r["code"])
    )

    def badge_html(text, kind):
        # kind: ok / warn / bad / info
        colors = {
            "ok":   "#2e7d32",
            "warn": "#f9a825",
            "bad":  "#c62828",
            "info": "#1565c0",
        }
        c = colors.get(kind, "#444")
        return f"<span style='display:inline-block;padding:2px 8px;border-radius:999px;border:1px solid {c};color:#eee;background:#121212;margin-right:6px;'>{html.escape(text)}</span>"

    rows = []
    for r in results_sorted:
        alerts = status_badges(r)
        badges = []
        if not alerts:
            badges.append(badge_html("OK", "ok"))
        else:
            for a in alerts:
                if a == "LOW_COVERAGE":
                    badges.append(badge_html("LOW_COVERAGE", "bad"))
                elif a == "MANY_ADDED":
                    badges.append(badge_html("MANY_ADDED", "warn"))
                elif a == "MANY_REMOVED":
                    badges.append(badge_html("MANY_REMOVED", "warn"))
                else:
                    badges.append(badge_html(a, "info"))

        rows.append(f"""
<tr>
  <td><b>{html.escape(r["code"])}</b></td>
  <td>{html.escape(str(r["lang_label"]))}</td>
  <td>{r["template_keys"]}</td>
  <td>{r["translated"]}</td>
  <td>{r["added"]} <small style="color:#aaa">({r["added_ratio"]:.2f}%)</small></td>
  <td>{r["removed"]} <small style="color:#aaa">({r["removed_ratio"]:.2f}%)</small></td>
  <td><b>{r["coverage"]:.1f}%</b></td>
  <td>{''.join(badges)}</td>
  <td><a href="{html.escape(r["report_rel"])}">Open report</a></td>
  <td><a href="{html.escape(r["out_rel"])}">Synced file</a></td>
</tr>
""")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>REAPER LangPack - Dashboard</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; background:#111; color:#eee; margin:20px; }}
.card {{ background:#1a1a1a; border:1px solid #333; border-radius:10px; padding:14px 16px; margin:12px 0; }}
table {{ border-collapse:collapse; width:100%; font-family: Consolas, monospace; }}
th,td {{ border-bottom:1px solid #2b2b2b; padding:8px 10px; text-align:left; }}
tr:hover {{ background:#171717; }}
a {{ color:#8ab4f8; text-decoration:none; }}
a:hover {{ text-decoration:underline; }}
small.muted {{ color:#aaa; }}
</style>
</head>
<body>
<h1>REAPER LangPack - Multi-language Dashboard</h1>

<div class="card">
  <div><small class="muted">Generated: {tnow}</small></div>
  <div><small class="muted">Template: {html.escape(str(TEMPLATE_FILE))} (tag: {html.escape(tag)})</small></div>
  <div><small class="muted">Thresholds: coverage &lt; {COVERAGE_ALERT_THRESHOLD:.1f}% , added &gt;= {ADDED_ALERT_THRESHOLD} , removed &gt;= {REMOVED_ALERT_THRESHOLD}</small></div>
  <div style="margin-top:8px;"><small class="muted">{HTML_HEADER_CREDIT}</small></div>
</div>

<div class="card">
  <h2>Results (sorted by lowest coverage)</h2>
  <table>
    <tr>
      <th>Code</th><th>Language name</th><th>Template keys</th>
      <th>Translated</th><th>Added</th><th>Removed</th><th>Coverage</th><th>Status</th><th>Report</th><th>Synced</th>
    </tr>
    {''.join(rows)}
  </table>
</div>

</body>
</html>
"""

# ============================================================
# RUN MULTI WITH PER-LANGUAGE FOLDERS
# ============================================================

def run_selected(codes_to_run):
    if not TEMPLATE_FILE.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_FILE}")

    BASE_OUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    errors = []

    for code in codes_to_run:
        src = LANGUAGES.get(code)
        if not src:
            errors.append(f"[{code}] not configured in LANGUAGES")
            continue
        if not src.exists():
            errors.append(f"[{code}] missing source file: {src}")
            continue

        try:
            lang_dir = BASE_OUT_DIR / code
            r = merge_one(TEMPLATE_FILE, src, lang_dir, code)
            results.append(r)
        except Exception as e:
            errors.append(f"[{code}] ERROR: {e}")

    # Always write dashboard if at least one success
    if results:
        dash = build_dashboard(results)
        with DASHBOARD_HTML.open("w", encoding="utf-8") as f:
            f.write(dash)

    return results, errors

# ============================================================
# MENU (double-click)
# ============================================================

def menu_select_codes():
    codes = sorted(LANGUAGES.keys())
    print("\n=== Multi-language menu ===")
    print("Template:", TEMPLATE_FILE)
    print("Output dir:", BASE_OUT_DIR)
    print("Template tag:", template_tag())
    print("\nAvailable languages:")
    for i, c in enumerate(codes, start=1):
        print(f"  {i}) {c} -> {LANGUAGES[c]}")
    print("\nOptions:")
    print("  A) All languages")
    print("  Q) Quit")

    choice = input("\nChoose (number / A / Q): ").strip().upper()

    if choice == "Q":
        return []
    if choice == "A":
        return codes

    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(codes):
            return [codes[idx - 1]]

    # Also allow direct code entry (TR, FR, ES ...)
    if choice in LANGUAGES:
        return [choice]

    print("Invalid choice.")
    return None

# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    try:
        # CLI single-language compatibility:
        # python merge_langpacks.py template.txt language.txt output.txt added.txt removed.txt
        if len(sys.argv) >= 6:
            # In CLI mode we keep "single run" behavior (no per-language folder enforced).
            template = Path(sys.argv[1])
            source   = Path(sys.argv[2])
            outp     = Path(sys.argv[3])
            added    = Path(sys.argv[4])
            removed  = Path(sys.argv[5])
            report   = Path(str(outp.with_suffix("")) + "_REPORT.html")

            # Reuse multi machinery by running a temporary "ONE" folder at outp.parent
            tmp_dir = outp.parent if str(outp.parent) else Path(".")
            tmp_code = "ONE"
            r = merge_one(template, source, tmp_dir, tmp_code)

            # Move/overwrite to requested names
            suffix = "_" + template.stem if INCLUDE_TEMPLATE_TAG_IN_FILENAMES else ""
            # We do not try to guess the exact suffix used above; instead locate by pattern.
            # We know merge_one used TEMPLATE_FILE globally, so here we use the generated names directly:
            # For CLI simplicity, just write again using merge_one logic would be larger; keep it minimal:
            # If you need CLI with per-language folders, tell me and I adapt.
            (tmp_dir / f"LangPack_{tmp_code}_SYNCED{maybe_tag_suffix()}.txt").replace(outp)
            (tmp_dir / f"LangPack_{tmp_code}_ADDED{maybe_tag_suffix()}.txt").replace(added)
            (tmp_dir / f"LangPack_{tmp_code}_REMOVED{maybe_tag_suffix()}.txt").replace(removed)
            (tmp_dir / f"LangPack_{tmp_code}_REPORT{maybe_tag_suffix()}.html").replace(report)

            print("Single merge complete.")
            print("Output:", outp.resolve())
            print("Added:", added.resolve())
            print("Removed:", removed.resolve())
            print("Report:", report.resolve())
        else:
            # Double-click mode: show menu
            while True:
                selected = menu_select_codes()
                if selected == []:
                    print("Quit.")
                    break
                if selected is None:
                    continue

                print("\nRunning:", ", ".join(selected))
                results, errors = run_selected(selected)

                print("\nDone.")
                if results:
                    print("Dashboard:", DASHBOARD_HTML.resolve())
                    for r in results:
                        print(f"{r['code']}: coverage {r['coverage']:.1f}% | added {r['added']} | removed {r['removed']} | report {r['report_rel']}")
                if errors:
                    print("\nWarnings/Errors:")
                    for e in errors:
                        print(" -", e)

                again = input("\nRun again? (Y/N): ").strip().upper()
                if again != "Y":
                    break

            input("\nPress Enter to close...")

    except Exception as e:
        print("ERROR:", e)
        input("Press Enter to close...")