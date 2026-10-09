#!/usr/bin/env python3
"""Draw the README's cards: the terminal, packages, merged PRs, projects,
section headings, the solar system's key and the footer links. Each gets a
dark SVG (space, to match the solar system) and a light one (engraved
parchment, to match the orrery), written to dist/.

What's shown lives in cards.json. Live numbers (downloads, stars, last push,
PR sizes, the AUR version) are fetched on every run so the Action keeps them
current. A source that fails draws a dash instead of taking the card down.

    python3 gen/cards.py            # write dist/*.svg
    python3 gen/cards.py --readme   # print the README markup for all of it
"""
import json
import math
import os
import random
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import solar  # noqa: E402  (textures, palettes, the repo fetch)

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = "https://raw.githubusercontent.com/shwetankg07/shwetankg07/output/"
USER = "shwetankg07"

MONO = 'ui-monospace,SFMono-Regular,"JetBrains Mono",Menlo,Consolas,monospace'
DARK = {
    "dark": True, "text": "#e6edf3", "muted": "#8b949e", "faint": "#30363d", "bg1": "#0d1117", "bg2": "#121a2d",
    "code_bg": "#161b22", "code": "#79c0ff", "key": "#79c0ff", "prompt": "#3fb950", "add": "#3fb950",
    "rem": "#f85149", "merge": "#a371f7", "hl": "#d2a8ff", "comment": "#6e7681",
    "title": MONO, "body": MONO, "italic": "normal",
}
LIGHT = {
    "dark": False, "text": "#3a2e22", "muted": "#76664f", "faint": "#c9b896", "bg1": "#f7f0df", "bg2": "#ede1c5",
    "code_bg": "#efe4c9", "code": "#6b4f1d", "key": "#8a5a1c", "prompt": "#a8834a", "add": "#4d7a3a",
    "rem": "#a0463c", "merge": "#6f4a8e", "hl": "#6f4a8e", "comment": "#9a8a70",
    "title": 'Georgia,"Times New Roman",serif', "body": '"Courier New",Courier,monospace', "italic": "italic",
}
ROMAN = ["I", "II", "III", "IV", "V", "VI"]


def get(url, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": "cards", "Accept": "application/json"})
    if url.startswith("https://api.github.com") and os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", "Bearer " + os.environ["GITHUB_TOKEN"])
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode()
            return body if raw else json.loads(body)
    except Exception as e:  # noqa: BLE001 - any failure just means "draw a dash"
        print(f"  {url}: {e}", file=sys.stderr)
        return None


def hexmix(a, b, t):
    return "#%02x%02x%02x" % tuple(int(k) for k in solar.mix(solar.rgb(a), solar.rgb(b), t))


def accent(lang, th):
    if th["dark"]:
        return solar.RAMP.get(lang, solar.RAMP_OTHER)[2]
    return hexmix(solar.WASH.get(lang, "#99938a"), th["text"], .45)


def txt(x, y, s, size, fill, th, weight=400, font=None, anchor="start", extra=""):
    font = font or th["body"]
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family=\'{font}\' font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{extra}>{escape(s)}</text>')


def title_txt(x, y, s, size, fill, th, anchor="start"):
    return txt(x, y, s, size, fill, th, weight=700, font=th["title"], anchor=anchor,
               extra=f' font-style="{th["italic"]}"')


def wrap(s, width):
    lines, line = [], ""
    for word in s.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + [line] if line else lines


def svg(w, h, body, label, css=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="{escape(label, {chr(34): "&quot;"})}"><title>{escape(label)}</title>'
            f'<style>{css}@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}'
            f'.l,.c{{opacity:1!important}}}}</style>{body}</svg>')


def frame(w, h, th, seed=None, border=None):
    """card background: a quiet dark panel with a hairline edge, or plain
    parchment with a single ink rule"""
    if not th["dark"]:
        return (f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" fill="{th["bg1"]}" stroke="{th["text"]}" '
                f'stroke-opacity=".55"/>')
    edge = (f'<defs><linearGradient id="edge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{border[0]}"/>'
            f'<stop offset="1" stop-color="{border[1]}"/></linearGradient></defs>') if border else ""
    return (f'{edge}<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="12" fill="#0f141b"/>'
            f'<line x1="24" x2="{w - 24}" y1="1" y2="1" stroke="#ffffff" stroke-opacity=".06"/>'
            f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="12" fill="none" '
            f'stroke="{"url(#edge)" if border else "#21262d"}"/>')


# --- the terminal ------------------------------------------------------------

def terminal(th, version):
    ch = 13.5 * .6
    lines = [
        ("prompt", "pacman -Qi shwetank"),
        ("kv", "Name", "shwetank"), ("kv", "Version", version or "2026.7.30-1"),
        ("kv", "Description", "builds products end to end, from the postgres schema to the pixel"),
        ("kv", "Architecture", "x86_64 (acer predator, arch btw)"),
        ("kv", "URL", "https://shwetank.is-a.dev"),
        ("kv", "Groups", "scaler-school-of-technology  bits-pilani"),
        ("kv", "Provides", "the tech at chalyaaar"),
        ("kv", "Depends On", "neovim  hyprland  typescript  python  postgres"),
        ("kv", "Optional Deps", "rust: learning"), ("kv", "", "docker: learning"), ("kv", "", "sleep: not installed"),
        ("kv", "Install Reason", "Explicitly installed"),
        ("blank",),
        ("comment", "# that one is real, by the way. so are these:"),
        ("cmd", "npx shwetank", "# a business card, in your terminal"),
        ("cmd", "curl shwetank.is-a.dev", "# same card, no node needed"),
        ("cmd", "yay -S shwetank", "# it's on the aur"),
        ("cmd", "git clone https://shwetank.is-a.dev", "# the website is also a git repo"),
        ("cursor",),
    ]
    w, x0, lh, top = 860, 28, 21, 68
    h = top + len(lines) * lh + 10
    glyph = "❯" if th["dark"] else "$"
    out, t = [], .5

    def typed(x, y, s, fill, t, rate):
        spans = "".join(f'<tspan class="c" style="animation-delay:{t + i * rate:.2f}s">{escape(c)}</tspan>'
                        for i, c in enumerate(s))
        return (f'<text x="{x:.1f}" y="{y:.1f}" font-family=\'{th["body"]}\' font-size="13.5" fill="{fill}" '
                f'xml:space="preserve">{spans}</text>'), t + len(s) * rate

    def shown(inner, t):
        return f'<g class="l" style="animation-delay:{t:.2f}s">{inner}</g>'

    for i, ln in enumerate(lines):
        y = top + i * lh
        kind = ln[0]
        if kind == "prompt":
            out.append(shown(txt(x0, y, glyph, 13.5, th["prompt"], th, 700), t))
            s, t = typed(x0 + 2 * ch, y, ln[1], th["text"], t + .3, .055)
            out.append(s)
            t += .35
        elif kind == "kv":
            key, val = ln[1], ln[2]
            parts = txt(x0, y, key, 13.5, th["key"], th) + (txt(x0 + 15 * ch, y, ":", 13.5, th["muted"], th) if key else "")
            if "arch btw" in val:  # the one bit that deserves colour
                head, _, tail = val.partition("arch btw")
                parts += (f'<text x="{x0 + 17 * ch:.1f}" y="{y}" font-family=\'{th["body"]}\' font-size="13.5" '
                          f'fill="{th["text"]}" xml:space="preserve">{escape(head)}<tspan fill="{th["hl"]}" '
                          f'font-weight="700">arch btw</tspan>{escape(tail)}</text>')
            else:
                parts += txt(x0 + 17 * ch, y, val, 13.5, th["text"], th, extra=' xml:space="preserve"')
            out.append(shown(parts, t))
            t += .05
        elif kind == "comment":
            t += .35
            out.append(shown(txt(x0, y, ln[1], 13.5, th["comment"], th), t))
            t += .3
        elif kind == "cmd":
            out.append(shown(txt(x0, y, glyph, 13.5, th["prompt"], th, 700), t))
            s, t = typed(x0 + 2 * ch, y, ln[1], th["text"], t + .1, .03)
            out.append(s)
            out.append(shown(txt(x0 + 40 * ch, y, ln[2], 13.5, th["comment"], th), t + .05))
            t += .25
        elif kind == "cursor":
            out.append(shown(txt(x0, y, glyph, 13.5, th["prompt"], th, 700)
                             + f'<rect class="blink" x="{x0 + 2 * ch:.1f}" y="{y - 11}" width="{ch:.1f}" height="15" '
                               f'fill="{th["text"]}"/>', t))

    bar = (txt(x0, 30, "shwetank@predator: ~", 12, th["muted"], th)
           + txt(w - x0, 30, "kitty", 12, th["muted"], th, anchor="end")
           + f'<line x1="14" x2="{w - 14}" y1="44" y2="44" stroke="{th["faint"]}" stroke-width="1"/>')
    css = (".l,.c{opacity:0;animation:on .01s linear forwards}.l{animation-duration:.2s}"
           "@keyframes on{to{opacity:1}}.blink{animation:blink 1.1s steps(1) infinite}@keyframes blink{50%{opacity:0}}")
    label = "a terminal running pacman -Qi shwetank, then npx shwetank, curl shwetank.is-a.dev, yay -S shwetank"
    return svg(w, h, frame(w, h, th, border=("#33ccff", "#00ff99")) + bar + "".join(out), label, css)


# --- packages ----------------------------------------------------------------

PILLS = {"npm": ("#cb3837", "#ffffff"), "pypi": ("#3775a9", "#ffd43b"), "aur": ("#1793d1", "#ffffff")}


def spark(series, x0, x1, y0, y1, colour, uid):
    """a thin line, 7-day averaged, ending in a dot"""
    if not series:
        return f'<line x1="{x0}" x2="{x1}" y1="{y1}" y2="{y1}" stroke="{colour}" stroke-dasharray="2 4" opacity=".35"/>'
    avg = [sum(series[max(0, i - 6):i + 1]) / len(series[max(0, i - 6):i + 1]) for i in range(len(series))]
    top = max(avg) or 1
    pts = [(x0 + (x1 - x0) * i / max(len(avg) - 1, 1), y1 - (y1 - y0) * v / top) for i, v in enumerate(avg)]
    line = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    ex, ey = pts[-1]
    return (f'<path class="draw" d="{line}" pathLength="1" fill="none" stroke="{colour}" stroke-width="1.4" '
            f'stroke-linejoin="round" stroke-linecap="round" opacity=".9"/>'
            f'<circle class="fade" cx="{ex:.1f}" cy="{ey:.1f}" r="2.6" fill="{colour}"/>')


def package(p, st, th, uid):
    w, h = 420, 150
    col = accent(p["lang"], th)
    out = [frame(w, h, th)]
    out.append(title_txt(22, 42, p["name"], 21, th["text"], th))
    out.append(txt(22, 63, p["note"], 12, th["muted"], th))
    out.append(txt(398, 42, st.get("total") or "—", 24, col, th, 600, anchor="end"))
    out.append(txt(398, 62, "downloads", 11, th["muted"], th, anchor="end"))
    out.append(spark(st.get("series"), 22, 398, 82, 112, col, uid))
    out.append(txt(22, 134, "$ " + p["install"], 12, th["code"], th, extra=' xml:space="preserve"'))
    meta = " · ".join(p["registries"] + (["v" + st["version"]] if st.get("version") else []))
    out.append(txt(398, 134, meta, 11, th["muted"], th, anchor="end"))
    css = (".draw{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 2s .3s ease-out forwards}"
           "@keyframes draw{to{stroke-dashoffset:0}}.fade{opacity:0;animation:fade .6s 2.1s forwards}"
           "@keyframes fade{to{opacity:1}}@media (prefers-reduced-motion:reduce){.draw{stroke-dashoffset:0}.fade{opacity:1}}")
    label = f"{p['name']}: {p['note']}. {st.get('total') or 'unknown'} downloads. install with {p['install']}"
    return svg(w, h, "".join(out), label, css)


def package_stats(p):
    st = {}
    if p.get("npm"):
        end = date.today()
        d = get(f"https://api.npmjs.org/downloads/range/{end - timedelta(days=540)}:{end}/{p['npm']}")
        if d and d.get("downloads"):
            days = [x["downloads"] for x in d["downloads"]]
            st["total"] = f"{sum(days):,}"
            st["series"] = days[-90:]
        v = get(f"https://registry.npmjs.org/{p['npm']}/latest")
        st["version"] = v and v.get("version")
    if p.get("pypi"):
        d = get(f"https://img.shields.io/pepy/dt/{p['pypi']}.json")
        st["total"] = d and d.get("value")
        d = get(f"https://pypistats.org/api/packages/{p['pypi']}/overall?mirrors=false")
        if d and d.get("data"):
            rows = sorted((r["date"], r["downloads"]) for r in d["data"] if r["category"] == "without_mirrors")
            st["series"] = [n for _, n in rows][-90:]
        v = get(f"https://pypi.org/pypi/{p['pypi']}/json")
        st["version"] = v and v["info"]["version"]
    return st


# --- merged PRs --------------------------------------------------------------

def merge_glyph(cx, cy, colour):
    """the git-merge mark: two branches meeting"""
    return (f'<g transform="translate({cx - 7},{cy - 8})" fill="none" stroke="{colour}" stroke-width="1.8" '
            f'stroke-linecap="round"><circle cx="3" cy="3" r="2.2"/><circle cx="3" cy="13" r="2.2"/>'
            f'<circle cx="12" cy="9" r="2.2"/><path d="M3 5.2v5.6M3 5.4c0 3 3 3.6 6.8 3.6"/></g>')


def pr_card(ref, info, th):
    w, h = 420, 118
    repo, num = ref.split("#")
    out = [frame(w, h, th), merge_glyph(29, 33, th["merge"])]
    short = repo if len(repo) <= 32 else repo[:31] + "…"
    out.append(txt(44, 37, short, 12, th["muted"], th) + txt(44 + len(short) * 7.2 + 6, 37, "#" + num, 12, th["merge"], th, 600))
    if info and info.get("additions") is not None:
        d = f"−{info['deletions']}"
        out.append(txt(398, 37, d, 12, th["rem"], th, anchor="end")
                   + txt(398 - len(d) * 7.2 - 8, 37, f"+{info['additions']}", 12, th["add"], th, anchor="end"))
    title = (info or {}).get("title") or ref
    for k, line in enumerate(wrap(title, 42)[:2]):
        out.append(title_txt(22, 66 + k * 19, line, 14, th["text"], th))
    if info and info.get("merged_at"):
        when = datetime.fromisoformat(info["merged_at"].replace("Z", "+00:00")).strftime("merged %b %-d, %Y").lower()
        out.append(txt(22, 104, when, 11, th["muted"], th))
    return svg(w, h, "".join(out), f"merged pull request {ref}: {title}")


# --- projects ------------------------------------------------------------------

def ago(iso):
    days = (datetime.now(timezone.utc) - datetime.fromisoformat(iso.replace("Z", "+00:00"))).days
    if days < 1:
        return "pushed today"
    if days < 2:
        return "pushed yesterday"
    if days < 14:
        return f"pushed {days}d ago"
    return f"pushed {days // 7}w ago" if days < 60 else f"pushed {days // 30}mo ago"


def icon(p, kind, th, cx, cy, r):
    """the repo's planet from the solar system, small and still spinning"""
    if kind == "probe":
        ink = "#c9d1d9" if th["dark"] else th["text"]
        panel = "#1f6feb" if th["dark"] else "none"
        return (f'<g transform="translate({cx},{cy}) scale(2.1)">'
                f'<rect x="-13" y="-1.6" width="8" height="3.2" fill="{panel}" stroke="{ink}" stroke-width=".6"/>'
                f'<rect x="5" y="-1.6" width="8" height="3.2" fill="{panel}" stroke="{ink}" stroke-width=".6"/>'
                f'<rect x="-3.5" y="-2.5" width="7" height="5" rx="1" fill="{ink}"/>'
                f'<line y1="-2.5" y2="-7" stroke="{ink}" stroke-width=".7"/><circle cy="-7.5" r="1.4" fill="#ff7b72"/></g>')
    out = []
    ring_rx = r * 1.75
    ring = lambda sweep: (f'<path d="M{-ring_rx:.1f},0A{ring_rx:.1f},{ring_rx * .36:.1f} 0 0 {sweep} {ring_rx:.1f},0" '
                          f'fill="none" stroke="{"#e8dcc0" if th["dark"] else th["text"]}" stroke-width="2" '
                          f'opacity="{.7 if th["dark"] else .9}"/>')
    if p.get("ring"):
        out.append(ring(1))
    if th["dark"]:
        glow = solar.RAMP.get(p["lang"], solar.RAMP_OTHER)[2] if kind != "moon" else "#9aa4b2"
        out.append(f'<defs><radialGradient id="gl"><stop offset=".45" stop-color="{glow}" stop-opacity=".2"/>'
                   f'<stop offset="1" stop-color="{glow}" stop-opacity="0"/></radialGradient>'
                   f'<radialGradient id="limb"><stop offset=".55" stop-opacity="0"/><stop offset=".9" stop-opacity=".4"/>'
                   f'<stop offset="1" stop-opacity=".75"/></radialGradient>'
                   f'<linearGradient id="sh" x1="1" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#01030a" stop-opacity=".85"/>'
                   f'<stop offset=".45" stop-color="#01030a" stop-opacity=".35"/><stop offset=".7" stop-color="#01030a" stop-opacity="0"/></linearGradient>'
                   f'<linearGradient id="rim" x1="1" y1="1" x2="0" y2="0"><stop offset=".55" stop-color="#e8f4ff" stop-opacity="0"/>'
                   f'<stop offset="1" stop-color="#e8f4ff" stop-opacity=".85"/></linearGradient>'
                   f'<clipPath id="unit"><circle r="1"/></clipPath>'
                   f'<image id="tx" width="4" height="2" preserveAspectRatio="none" href="{solar.planet_texture(p)}"/></defs>')
        out.insert(0, f'<circle r="{r * 1.9:.1f}" fill="url(#gl)"/>')
        out.append(f'<g transform="scale({r})"><g clip-path="url(#unit)"><g class="roll"><use href="#tx" x="-1" y="-1"/>'
                   f'<use href="#tx" x="3" y="-1"/></g></g><circle r="1" fill="url(#limb)"/></g>'
                   f'<circle r="{r}" fill="url(#sh)"/><circle r="{r - .7:.1f}" fill="none" stroke="url(#rim)" stroke-width="1.3"/>')
    else:
        wash = solar.WASH.get(p["lang"], "#99938a") if kind != "moon" else "#b5ad9f"
        out.append(f'<defs><radialGradient id="w"><stop offset="0" stop-color="#fbf6ea"/><stop offset="1" stop-color="{wash}"/>'
                   f'</radialGradient><pattern id="hatch" width="2.6" height="2.6" patternUnits="userSpaceOnUse" '
                   f'patternTransform="rotate(35)"><line y2="2.6" stroke="{th["text"]}" stroke-width=".75"/></pattern></defs>'
                   f'<circle r="{r}" fill="url(#w)"/>'
                   f'<path d="M0,{-r}A{r},{r} 0 0 1 0,{r}A{r * .4:.1f},{r} 0 0 0 0,{-r}Z" fill="url(#hatch)" '
                   f'transform="rotate(45)"/><circle r="{r}" fill="none" stroke="{th["text"]}" stroke-width="1"/>')
    if p.get("ring"):
        out.append(ring(0))
    for k in range(min(p.get("moons", 0), 4)):
        a = math.radians(-30 + k * 70)
        mx, my = (r + 8) * math.cos(a), (r + 8) * math.sin(a) * .5 - 4
        fill = "#b9c2cd" if th["dark"] else "#f3ead6"
        out.append(f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="2.6" fill="{fill}" stroke="{th["text"] if not th["dark"] else "none"}" stroke-width=".7"/>')
    return f'<g transform="translate({cx},{cy})">{"".join(out)}</g>'


def project(pr, meta, th):
    w, h = 420, 124
    lang = meta.get("language")
    col = accent(lang, th)
    kind = "probe" if pr["repo"] == "great-consolidation" else "moon" if pr["repo"] == "railpull" else "planet"
    p = {"name": pr["repo"], "lang": None if kind == "moon" else lang,
         "pr": 6 + 3.6 * math.log10(meta.get("size", 0) + 10),
         "ring": meta.get("ring"), "moons": meta.get("moons", 0)}
    out = [frame(w, h, th), icon(p, kind, th, 54, 58, 16 if kind == "moon" else 23)]
    out.append(title_txt(98, 40, pr["repo"], 17, th["text"], th))
    if pr.get("private"):
        tx = 98 + len(pr["repo"]) * (10.2 if th["dark"] else 9) + 10
        out.append(f'<rect x="{tx:.0f}" y="27" width="54" height="17" rx="8.5" fill="none" stroke="{th["muted"]}"/>'
                   + txt(tx + 27, 39.5, "private", 10.5, th["muted"], th, anchor="middle"))
    for k, line in enumerate(wrap(pr["note"], 41)[:2]):
        out.append(txt(98, 63 + k * 17, line, 12.5, th["muted"], th))
    bits = [(f"● {lang}" if lang else None, col)]
    if meta.get("stargazers_count"):
        bits.append((f"  {meta['stargazers_count']}", th["text"]))  # the star itself is drawn below
    if meta.get("pushed_at"):
        bits.append((ago(meta["pushed_at"]), th["muted"]))
    x = 98
    for s, c in bits:
        if s:
            if s.startswith("  "):  # draw the star, some mono fonts lack the glyph
                pts = " ".join(f"{x + 5 + (5 if k % 2 == 0 else 2.1) * math.sin(math.pi * k / 5):.1f},"
                               f"{104 - (5 if k % 2 == 0 else 2.1) * math.cos(math.pi * k / 5):.1f}" for k in range(10))
                out.append(f'<polygon points="{pts}" fill="{"#e3b341" if th["dark"] else th["key"]}"/>')
            out.append(txt(x, 108, s, 11.5, c, th, extra=' xml:space="preserve"'))
            x += len(s) * 7.1 + 16
    css = ".roll{animation:roll 30s linear infinite}@keyframes roll{to{transform:translateX(-4px)}}"
    return svg(w, h, "".join(out), f"{pr['repo']}: {pr['note']}", css)


# --- headings, the key, the footer ---------------------------------------------

def heading(text, n, th):
    w, h = 860, 48
    if th["dark"]:
        tw = len(text) * 12
        body = (txt(2, 32, "❯", 18, "#58a6ff", th, 700) + txt(28, 32, text, 20, th["text"], th, 600)
                + f'<line x1="{28 + tw + 18:.0f}" x2="{w - 2}" y1="26" y2="26" stroke="#21262d"/>')
    else:
        cap = text.upper()
        tw = len(cap) * 16.5
        body = (txt(2, 31, cap, 16, th["text"], th, 700, font=th["title"], extra=' letter-spacing="4.5"')
                + f'<line x1="{tw + 18:.0f}" x2="{w - 80}" y1="26" y2="26" stroke="{th["text"]}" stroke-width=".6"/>'
                + txt(w - 2, 31, f"Tab. {ROMAN[n]}.", 14, th["text"], th, font=th["title"], anchor="end",
                      extra=f' font-style="{th["italic"]}"'))
    return svg(w, h, body, text)


def key(th):
    """the solar system's legend, drawn as a proper map key"""
    w, h = 860, 150
    ink, mut = th["text"], th["muted"]
    lit = "#e6edf3" if th["dark"] else ink
    cells = [
        ("the sun", "me", f'<circle r="9" fill="{"#ffb347" if th["dark"] else "#d8b46a"}" stroke="{ink if not th["dark"] else "none"}"/>'),
        ("a planet", "a public repo, sized by code", f'<circle r="7" fill="{"#2f6fed" if th["dark"] else "#7d97b8"}" stroke="{ink if not th["dark"] else "none"}"/>'),
        ("colour", "its main language", "".join(f'<circle cx="{-8 + 8 * i}" r="3.6" fill="{c}"/>' for i, c in enumerate(
            ("#62a4ff", "#f0bd4f", "#58cdbb") if th["dark"] else ("#7d97b8", "#cfae5c", "#6fa59c")))),
        ("distance", "newer repos orbit closer", "".join(
            f'<ellipse rx="{r}" ry="{r * .42:.1f}" fill="none" stroke="{mut}" stroke-width=".9"/>' for r in (5, 9, 13))),
        ("a ring", "published to a registry", f'<circle r="6" fill="{"#d69e16" if th["dark"] else "#cfae5c"}"/>'
         f'<ellipse rx="12" ry="4" fill="none" stroke="{"#e8dcc0" if th["dark"] else ink}" stroke-width="1.6"/>'),
        ("moons", "sub-projects and merged PRs", f'<circle r="6" fill="{"#139c8e" if th["dark"] else "#6fa59c"}"/>'
         + "".join(f'<circle cx="{x}" cy="{y}" r="2.2" fill="{"#b9c2cd" if th["dark"] else "#f3ead6"}" stroke="{ink}" stroke-width=".5"/>'
                   for x, y in ((11, -3), (-10, 4)))),
        ("a comet", "pushed in the last day", f'<path d="M-2,-1.6L14,-7L14,-5Z" fill="{lit}" opacity=".5"/>'
         f'<path d="M-2,-1.2L16,4L15,6Z" fill="{lit}" opacity=".3"/><circle cx="-3" r="2.6" fill="{lit}"/>'),
        ("the probe", "the bot that commits daily", f'<g transform="scale(1.1)"><rect x="-13" y="-1.6" width="8" height="3.2" '
         f'fill="{"#1f6feb" if th["dark"] else "none"}" stroke="{lit}" stroke-width=".6"/><rect x="5" y="-1.6" width="8" '
         f'height="3.2" fill="{"#1f6feb" if th["dark"] else "none"}" stroke="{lit}" stroke-width=".6"/>'
         f'<rect x="-3.5" y="-2.5" width="7" height="5" rx="1" fill="{lit}"/></g>'),
    ]
    out = [frame(w, h, th)]
    for i, (term, meaning, glyph) in enumerate(cells):
        cx, cy = 22 + (i % 4) * 208, 36 + (i // 4) * 44
        out.append(f'<g transform="translate({cx + 14},{cy})">{glyph}</g>')
        out.append(title_txt(cx + 38, cy - 3, term, 13, ink, th) + txt(cx + 38, cy + 13, meaning, 11, mut, th))
    out.append(f'<line x1="22" x2="{w - 22}" y1="112" y2="112" stroke="{th["faint"]}"/>')
    out.append(txt(w / 2, 134, "click the system to open it, then any planet · orbits follow kepler · glow is stars · redrawn every 6h", 11.5, mut, th, anchor="middle"))
    return svg(w, h, "".join(out), "key: sun is me, planets are repos sized by code and coloured by language, "
               "newer repos orbit closer, rings mean published, moons are sub-projects and merged PRs, "
               "comets were pushed today, the probe is a daily bot")


def pill(label, glyph, th):
    w, h = int(46 + len(label) * 7.6), 40
    if th["dark"]:
        body = frame(w, h, th).replace('rx="12"', 'rx="20"')
    else:
        body = (f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="19" fill="{th["bg1"]}" stroke="{th["text"]}" '
                f'stroke-width="1.2"/>')
    body += txt(20, 25.5, glyph, 14, "#58a6ff" if th["dark"] else th["prompt"], th, 700, anchor="middle")
    body += txt(34, 25, label, 13, th["text"], th)
    return svg(w, h, body, label)


# --- run ---------------------------------------------------------------------------

def slug(s):
    return "".join(c if c.isalnum() or c in "-_." else "-" for c in s)


LINKS = [("site", "shwetank.is-a.dev", "↗", "https://shwetank.is-a.dev"),
         ("linkedin", "linkedin", "↗", "https://www.linkedin.com/in/shwetankg07"),
         ("mail", "shwetankg07@gmail.com", "✉", "mailto:shwetankg07@gmail.com")]
HEADINGS = ["shipped", "merged upstream", "~/work"]


def build():
    cfg = json.load(open(os.path.join(HERE, "cards.json")))
    sol = {p["repo"]: p for p in json.load(open(os.path.join(HERE, "solar.json")))["planets"]}
    moon_count = {name: len(p["moons"]) if isinstance(p.get("moons"), list) else p.get("moons", 0)
                  for name, p in sol.items()}
    try:
        repos = solar.fetch(USER)
    except Exception as e:  # noqa: BLE001
        print(f"  repos: {e}", file=sys.stderr)
        repos = {}
    aur = get("https://aur.archlinux.org/rpc/v5/info?arg[]=shwetank")
    version = aur and aur.get("results") and aur["results"][0]["Version"]
    stats = {p["name"]: package_stats(p) for p in cfg["packages"]}
    prs = {}
    for ref in cfg["prs"]:
        repo, num = ref.split("#")
        prs[ref] = get(f"https://api.github.com/repos/{repo}/pulls/{num}")

    files = {}
    for name, th in (("dark", DARK), ("light", LIGHT)):
        files[f"terminal-{name}"] = terminal(th, version)
        files[f"key-{name}"] = key(th)
        for i, text in enumerate(HEADINGS, 1):
            files[f"h-{slug(text)}-{name}"] = heading(text, i, th)
        for i, p in enumerate(cfg["packages"]):
            files[f"pkg-{slug(p['name'])}-{name}"] = package(p, stats[p["name"]], th, i)
        for ref in cfg["prs"]:
            files[f"pr-{slug(ref)}-{name}"] = pr_card(ref, prs[ref], th)
        for pr in cfg["projects"]:
            meta = dict(pr.get("private") or repos.get(pr["repo"], {}))
            meta["ring"] = sol.get(pr["repo"], {}).get("ring")
            meta["moons"] = moon_count.get(pr["repo"], 0)
            files[f"proj-{slug(pr['repo'])}-{name}"] = project(pr, meta, th)
        for key_, label, glyph, _ in LINKS:
            files[f"link-{key_}-{name}"] = pill(label, glyph, th)
    os.makedirs(solar.OUT, exist_ok=True)
    for stem, body in files.items():
        with open(os.path.join(solar.OUT, stem + ".svg"), "w") as f:
            f.write(body)
    print(f"{len(files)} cards written")


def pic(stem, alt, size='width="100%"', href=None):
    tag = (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{RAW}{stem}-dark.svg">'
           f'<img alt="{escape(alt, {chr(34): "&quot;"})}" src="{RAW}{stem}-light.svg" {size}></picture>')
    return f'<a href="{href}">{tag}</a>' if href else tag


def readme():
    """the README markup for everything this script draws, keyed by section"""
    cfg = json.load(open(os.path.join(HERE, "cards.json")))
    gh = f"https://github.com/{USER}/"
    grid = lambda items: "<p>\n" + "\n".join(items) + "\n</p>"
    return {
        "key": pic("key", "key: the sun is me, planets are public repos sized by code and coloured by language, "
                          "newer ones orbit closer, rings are published packages, moons are sub-projects and merged "
                          "PRs, comets were pushed today, the probe is a daily bot"),
        "terminal": pic("terminal", "$ pacman -Qi shwetank. builds products end to end, from the postgres schema to "
                                    "the pixel. try npx shwetank, curl shwetank.is-a.dev or yay -S shwetank"),
        "headings": {t: pic(f"h-{slug(t)}", t) for t in HEADINGS},
        "packages": grid(pic(f"pkg-{slug(p['name'])}", f"{p['name']}: {p['note']}", 'width="49%"', p["href"])
                         for p in cfg["packages"]),
        "prs": grid(pic(f"pr-{slug(r)}", f"merged: {r}", 'width="49%"',
                        f"https://github.com/{r.split('#')[0]}/pull/{r.split('#')[1]}") for r in cfg["prs"]),
        "projects": grid(pic(f"proj-{slug(p['repo'])}", f"{p['repo']}: {p['note']}", 'width="49%"',
                             p.get("href") or gh + p["repo"]) for p in cfg["projects"]),
        "links": '<p align="center">\n' + "\n".join(pic(f"link-{k}", label, 'height="40"', href)
                                                  for k, label, _, href in LINKS) + "\n</p>",
    }


if __name__ == "__main__":
    if "--readme" in sys.argv:
        print(json.dumps(readme(), indent=2))
    else:
        build()
