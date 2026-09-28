#!/usr/bin/env python3
"""Draw the solar system at the bottom of the profile README.

Which repos are planets lives in solar.json. Size, language, age, stars and
last push come from the GitHub API (one call, works without a token).
Writes dist/solar-dark.svg and dist/solar-light.svg. Stdlib only: planet,
sun, corona and sky textures are procedural noise written out as tiny PNGs
and embedded, because an SVG inside an <img> can't load anything.

All motion is CSS (plus SMIL for the belt), because GitHub serves the SVG as
an image. Each body sits on a circle that one animation spins and
scale(1, TILT) squashes into an ellipse. A counter-spin with the same
duration and delay undoes the rotation and the squash for the body itself,
so planets stay round while their path is tilted. Everything that has to stay
in step with the orbit (which half it is on, how big it looks, which side the
sun lights) runs on that same clock.
"""
import base64
import json
import math
import os
import random
import struct
import sys
import urllib.request
import zlib
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "dist")

W, H = 1200, 660
CX, CY = 600, 330
TILT = 0.42             # ry / rx of every orbit: how steeply we look down
R_IN, R_OUT = 125, 470  # innermost and outermost planet orbits
PROBE_R = 84
BELT = (498, 548)
T_IN = 18.0             # seconds per orbit at R_IN, the rest follow Kepler
DEPTH = 0.2             # how much bigger a planet looks on the near side
SUN_R = 36

# dark-mode surface colours per language, deep to bright
RAMP = {
    "TypeScript": ("#0a2463", "#1d5bd8", "#62a4ff", "#d8e9ff"),
    "JavaScript": ("#4a2c05", "#b3730f", "#f0bd4f", "#fff1c9"),
    "Python": ("#053833", "#0f7f73", "#58cdbb", "#d6fff6"),
    "HTML": ("#46102c", "#a3336a", "#ec82b4", "#ffdcec"),
    "CSS": ("#211150", "#5a3cc4", "#a68fff", "#e9e0ff"),
    "Java": ("#430c09", "#a33420", "#ea7c5f", "#ffd9cb"),
    "Rust": ("#431c06", "#ad521b", "#ee9b58", "#ffe2c6"),
    "C": ("#1b2029", "#475264", "#97a2b3", "#e6ebf1"),
}
RAMP_OTHER = ("#22262d", "#5b636e", "#a7b0bb", "#eef1f4")
WASH = {  # light-mode watercolour per language
    "TypeScript": "#7d97b8", "JavaScript": "#cfae5c", "Python": "#6fa59c", "HTML": "#bf8aa2",
    "CSS": "#9a8bbd", "Java": "#b36e66", "Rust": "#b98760", "C": "#8f98a3",
}

DARK = {
    "dark": True, "phi": -9,  # the whole system sits at a slight diagonal
    "font": 'ui-monospace,SFMono-Regular,"JetBrains Mono",Menlo,Consolas,monospace',
    "label": "#adbac7", "halo": "#0b1020", "orbit": "#8b949e", "orbit_op": 0.2,
    "belt": "#8b95a3", "moon": "#b9c2cd", "probe": "#c9d1d9", "comet": "#d6e6ff", "shade": "#01030a",
}
LIGHT = {
    "dark": False, "phi": 0,
    "font": 'Georgia,"Times New Roman",serif',
    "label": "#3a2e22", "halo": "#f3ead6", "orbit": "#3a2e22", "orbit_op": 0.32,
    "belt": "#5a4a38", "moon": "#f3ead6", "ring": "#6b5232", "probe": "#3a2e22",
    "comet": "#3a2e22", "shade": "#3a2e22", "brass": "#a8834a",
}


def period(r):
    return T_IN * (r / R_IN) ** 1.5  # Kepler's third law


def clock(T, delay):
    return f'style="animation-duration:{T:.2f}s;animation-delay:{-delay:.2f}s"'


# --- data ------------------------------------------------------------------

def fetch(user):
    req = urllib.request.Request(
        f"https://api.github.com/users/{user}/repos?per_page=100&type=owner",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "solar"},
    )
    if os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", "Bearer " + os.environ["GITHUB_TOKEN"])
    # ponytail: one page of 100 repos, add paging past that
    with urllib.request.urlopen(req, timeout=30) as r:
        return {x["name"]: x for x in json.load(r) if not x["fork"]}


def model(cfg, repos):
    user, probe = cfg["user"], cfg["probe"]
    taken = {user, probe}
    planets = []
    for p in cfg["planets"]:
        src = p.get("private") or repos.get(p["repo"])
        if not src:
            print(f"skipping {p['repo']}: not a public repo", file=sys.stderr)
            continue
        moons = p.get("moons", 0)
        if isinstance(moons, list):
            taken.update(moons)
            moons = len(moons)
        taken.add(p["repo"])
        planets.append({
            "name": p["repo"],
            "lang": src.get("language"),
            "kb": src.get("size", 0),
            "stars": src.get("stargazers_count", 0),
            "created": src["created_at"],
            "ring": p.get("ring", False),
            "moons": moons,
        })
    planets.sort(key=lambda p: p["created"], reverse=True)  # newest orbit closest
    n = len(planets)
    for i, p in enumerate(planets):
        p["r"] = R_IN + (R_OUT - R_IN) * i / max(n - 1, 1)
        p["pr"] = 6 + 3.6 * math.log10(p["kb"] + 10)
        # golden-angle start positions: the first frame is always the same, so spread it
        p["phase"] = (i * 137.508 + 25) % 360 / 360

    now = datetime.now(timezone.utc)
    recent = [
        r for name, r in repos.items()
        if name not in taken
        and now - datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00")) < timedelta(days=1)
    ]
    recent.sort(key=lambda r: r["pushed_at"], reverse=True)
    return {
        "planets": planets,
        "probe": probe if probe in repos else None,
        "belt": sorted(n for n in repos if n not in taken),
        "comets": [r["name"] for r in recent[:3]],
    }


# --- textures --------------------------------------------------------------

class Noise:
    """value noise that wraps every `period` units in x, so textures tile"""

    def __init__(self, seed, period):
        rnd = random.Random(seed)
        self.p = period
        self.v = [rnd.random() for _ in range(period * 256)]

    def __call__(self, x, y):
        xi, yi = math.floor(x), math.floor(y)
        fx, fy = x - xi, y - yi
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        p, v = self.p, self.v
        x0, x1, y0, y1 = xi % p, (xi + 1) % p, (yi % 256) * p, ((yi + 1) % 256) * p
        a = v[x0 + y0] + (v[x1 + y0] - v[x0 + y0]) * fx
        b = v[x0 + y1] + (v[x1 + y1] - v[x0 + y1]) * fx
        return a + (b - a) * fy


def fbm(n, x, y, octaves):
    total, amp, norm = 0.0, 1.0, 0.0
    for _ in range(octaves):
        total += amp * n(x, y)
        norm += amp
        amp, x, y = amp * 0.5, x * 2, y * 2
    return total / norm


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def mix(a, b, t):
    return tuple(a[k] + (b[k] - a[k]) * t for k in range(len(a)))


def ramp_at(stops, t):
    t = min(max(t, 0.0), 1.0) * (len(stops) - 1)
    i = min(int(t), len(stops) - 2)
    return mix(stops[i], stops[i + 1], t - i)


def clamp(t):
    return min(max(t, 0.0), 1.0)


def png(w, h, px, channels):
    """px is a flat list of 0-255 values; rows use the Sub filter, which
    smooth noise compresses far better under"""
    stride, raw = w * channels, bytearray()
    for y in range(h):
        row = [min(255, max(0, int(v))) for v in px[y * stride:(y + 1) * stride]]
        raw.append(1)
        raw += bytes(row[:channels])
        raw += bytes((row[i] - row[i - channels]) & 255 for i in range(channels, stride))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    color = 6 if channels == 4 else 2
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, color, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))
    return "data:image/png;base64," + base64.b64encode(data).decode()


def planet_texture(p):
    """one full turn of the surface, 2:1, tiling left to right"""
    w, h = 128, 64
    stops = [rgb(c) for c in RAMP.get(p["lang"], RAMP_OTHER)]
    rnd = random.Random("tex" + p["name"])
    n = Noise(p["name"], 8)
    gas = p["pr"] >= 15
    bands = rnd.uniform(5, 9)
    su, sv = rnd.random(), rnd.uniform(0.3, 0.7)
    storm = mix(stops[3], (235, 110, 80), 0.55)
    px = []
    for y in range(h):
        v = (y + 0.5) / h
        for x in range(w):
            u = (x + 0.5) / w
            if gas:
                t = fbm(n, u * 8, v * 6, 4)
                band = math.sin((v * bands + (t - 0.5) * 2.2) * math.pi * 2)
                fine = fbm(n, u * 32, v * 40 + 50, 3)
                c = ramp_at(stops, 0.5 + 0.17 * band + 0.3 * (t - 0.5) + 0.3 * (fine - 0.5))
                du = min(abs(u - su), 1 - abs(u - su)) * 2
                d = (du / 0.1) ** 2 + ((v - sv) / 0.055) ** 2
                if d < 1:
                    c = mix(c, storm, (1 - d) ** 0.6 * 0.85)
            else:
                e = fbm(n, u * 8, v * 4 + 20, 5)
                if e < 0.5:
                    c = ramp_at(stops[:3], e / 0.5 * 0.75)  # sea
                else:
                    c = ramp_at(stops[1:], 0.3 + (e - 0.5) * 2.4)  # land
                c = mix(c, (236, 243, 250), clamp((abs(v - 0.5) - 0.36) / 0.1) * 0.9)  # ice caps
            px += c
    return png(w, h, px, 3)


def sun_texture():
    w, h = 192, 96
    n = Noise("sun", 16)
    stops = [(196, 66, 8), (250, 136, 28), (255, 202, 104), (255, 247, 218)]
    px = []
    for y in range(h):
        v = (y + 0.5) / h
        for x in range(w):
            u = (x + 0.5) / w
            g = fbm(n, u * 48, v * 24, 3) * 0.6 + fbm(n, u * 8, v * 4 + 90, 3) * 0.4
            px += ramp_at(stops, g * 1.6 - 0.25)
    return png(w, h, px, 3)


def corona_texture():
    """streaky light around the sun; drawn 10x the sun's radius, spun slowly"""
    s = 144
    c0, R = s / 2, s / 20
    n = Noise("corona", 32)
    px = []
    for y in range(s):
        for x in range(s):
            dx, dy = x + 0.5 - c0, y + 0.5 - c0
            d = math.hypot(dx, dy) / R
            a = (math.atan2(dy, dx) / (2 * math.pi)) % 1
            streak = clamp((fbm(n, a * 32, d * 0.5, 4) - 0.38) / 0.5) ** 1.7
            fall = math.exp(-(d - 1) * 0.9) if d > 1 else 1
            soft = math.exp(-(d - 1) * 2.6) if d > 1 else 1
            alpha = clamp(fall * streak * 1.3 + soft * 0.7) * clamp((9.2 - d) / 2.5)
            px += mix((255, 160, 70), (255, 238, 205), streak) + (alpha * 255,)
    return png(s, s, px, 4)


def sky_texture():
    """nebula and a milky way band, baked onto the page colour so the edges
    vanish into GitHub's background; low-res, it's all soft anyway"""
    w, h = 240, 132
    n1, n2, n3 = Noise("sky1", 64), Noise("sky2", 64), Noise("sky3", 64)
    centre, edge = (12, 20, 46), (13, 17, 23)
    hues = [(110, 64, 201), (31, 111, 235), (40, 150, 190), (219, 97, 162)]
    lx, ly = math.cos(math.radians(-24)), math.sin(math.radians(-24))  # band direction
    px = []
    for y in range(h):
        v = (y + 0.5) / h
        for x in range(w):
            u = (x + 0.5) / w
            base = mix(centre, edge, clamp(math.hypot(u - 0.5, (v - 0.5) * h / w) / 0.55))
            win = clamp(math.sin(math.pi * u) * 1.6) * clamp(math.sin(math.pi * v) * 1.6)
            q = fbm(n1, u * 4, v * 2.2, 4)
            dens = clamp((fbm(n2, u * 5 + q * 2.2, v * 2.8 + q * 2.2, 5) - 0.44) / 0.3) ** 1.4
            col = ramp_at(hues, fbm(n3, u * 2, v * 1.2, 3) * 1.6 - 0.3)
            # distance from the milky way's centre line, in canvas units
            X, Y = (u - 0.5) * W, (v - 0.55) * H
            dist = abs(-ly * X + lx * Y) / W
            band = math.exp(-(dist / 0.085) ** 2) * (0.55 + 0.9 * (fbm(n3, u * 9, v * 5 + 40, 4) - 0.5))
            lane = clamp((fbm(n1, u * 12, v * 7 + 70, 4) - 0.55) / 0.15) * math.exp(-(dist / 0.03) ** 2)
            glow = band * (1 - 0.7 * lane)
            px += tuple(base[k] + (col[k] * dens * 0.3 + (170, 185, 225)[k] * glow * 0.14) * win for k in range(3))
    return png(w, h, px, 3)


# --- pieces ----------------------------------------------------------------

def orbiting(r, T, delay, body, layer, arm=""):
    """body drawn at radius r around the current origin, on the 'f'ront or
    'b'ack half of its orbit (the other half is hidden in this copy)."""
    c = clock(T, delay)
    return (
        f'<g class="{layer}" {c}><g transform="scale(1,{TILT})"><g class="o" {c}>{arm}'
        f'<g transform="translate({r:.1f},0)"><g class="c" {c}>'
        f'<g transform="scale(1,{1 / TILT:.4f})">{body}</g></g></g></g></g></g>'
    )


def upright(svg, th):
    """labels live inside the tilted system; turn them back level"""
    return f'<g transform="rotate({-th["phi"]})">{svg}</g>' if th["phi"] else svg


def lang_key(lang):
    return (lang or "other").replace("+", "p").replace("#", "s").replace(" ", "")


def planet(p, i, th):
    pr, key = p["pr"], lang_key(p["lang"])
    rnd = random.Random(p["name"])
    T = period(p["r"])
    delay = p["phase"] * T
    c = clock(T, delay)
    back, front, defs = [], [], []

    if th["dark"]:
        glow = pr * (1.9 + 0.12 * math.sqrt(p["stars"]))
        back.append(f'<circle r="{glow:.1f}" fill="url(#glow-{key})" opacity="{min(1, .32 + .06 * p["stars"]):.2f}"/>')
    elif p["stars"]:
        g = pr + 3 + 2.2 * math.sqrt(p["stars"])
        back.append(f'<circle r="{g:.1f}" fill="none" stroke="{th["label"]}" '
                    f'stroke-width=".7" stroke-dasharray="1 2.4" opacity=".75"/>')

    if p["ring"]:
        if th["dark"]:  # banded, with a gap, like the real thing
            bands = ((1.38, 1.2, .3), (1.55, 2.6, .55), (1.72, 1.2, .35), (1.93, 3.2, .5), (2.12, 1.1, .28))
            colour = mix(rgb(RAMP.get(p["lang"], RAMP_OTHER)[3]), (232, 220, 192), .6)
            colour = "#%02x%02x%02x" % tuple(int(k) for k in colour)
        else:
            bands, colour = ((1.7, 1.1, .9), (2.05, .6, .7)), th["ring"]
        for k, w, op in bands:
            rx, ry = pr * k, pr * k * TILT
            for sweep, bucket in ((1, back), (0, front)):
                bucket.append(f'<path d="M{-rx:.1f},0A{rx:.1f},{ry:.1f} 0 0 {sweep} {rx:.1f},0" '
                              f'fill="none" stroke="{colour}" stroke-width="{w}" opacity="{op}"/>')

    for k in range(p["moons"]):
        mr, mT = pr + 8 + 5.5 * k, 3.6 + 1.9 * k
        md, size = rnd.uniform(0, mT), 2.2 + 0.8 * (k % 2)
        m = (f'<circle r="{size}" fill="url(#moon)"/>' if th["dark"] else
             f'<circle r="{size}" fill="{th["moon"]}" stroke="{th["label"]}" stroke-width=".7"/>')
        back.append(orbiting(mr, mT, md, m, "b"))
        front.append(orbiting(mr, mT, md, m, "f"))

    if th["dark"]:
        defs.append(f'<image id="tx{i}" width="4" height="2" preserveAspectRatio="none" href="{planet_texture(p)}"/>')
        day = rnd.uniform(14, 26) if pr >= 15 else rnd.uniform(24, 44)
        body = [
            f'<g transform="scale({pr:.2f})"><g clip-path="url(#unit)">'
            f'<g class="roll" style="animation-duration:{day:.1f}s"><use href="#tx{i}" x="-1" y="-1"/>'
            f'<use href="#tx{i}" x="3" y="-1"/></g></g><circle r="1" fill="url(#limb)"/></g>',
            f'<g class="s" {c}><circle r="{pr:.1f}" fill="url(#shade)"/>'
            f'<circle r="{pr - .6:.1f}" fill="none" stroke="url(#rim)" stroke-width="1.4"/></g>',
        ]
    else:
        body = [f'<circle r="{pr:.1f}" fill="url(#p-{key})"/>']
        if pr >= 13:
            lines = []
            for _ in range(3):
                y = rnd.uniform(-pr * .8, pr * .6)
                lines.append(f'<line x1="{-pr:.1f}" x2="{pr:.1f}" y1="{y:.1f}" y2="{y:.1f}" '
                             f'stroke="{th["label"]}" stroke-width=".5" opacity=".6"/>')
            body.append(f'<g clip-path="url(#cp{i})">{"".join(lines)}</g>')
            defs.append(f'<clipPath id="cp{i}"><circle r="{pr:.1f}"/></clipPath>')
        # engraved shadow: hatching over the far half, terminator bulging into it
        body.append(
            f'<g class="s" {c}><path d="M0,{-pr:.1f}A{pr:.1f},{pr:.1f} 0 0 0 0,{pr:.1f}'
            f'A{pr * .4:.1f},{pr:.1f} 0 0 1 0,{-pr:.1f}Z" fill="url(#hatch)"/></g>'
            f'<circle r="{pr:.1f}" fill="none" stroke="{th["label"]}" stroke-width=".9"/>')

    label = upright(f'<text y="{pr + 17:.1f}" class="lb">{p["name"]}</text>', th)
    inner = f'{label}<g class="d" {c}>{"".join(back + body + front)}</g>'
    arm = ""
    if not th["dark"]:
        arm = (f'<line x2="{p["r"]:.1f}" stroke="{th["brass"]}" stroke-width="1.1" '
               f'vector-effect="non-scaling-stroke" opacity=".85"/>')
    return "".join(defs), (lambda layer: orbiting(p["r"], T, delay, inner, layer, arm))


def trail(p, th):
    """a fading arc that follows each planet round, drawn in the flat orbit
    plane so it rides the same spin"""
    colour = RAMP.get(p["lang"], RAMP_OTHER)[2]
    T = period(p["r"])
    r, segs, span = p["r"], 14, 70
    arcs = []
    for k in range(segs):
        a1, a2 = math.radians(-span * (k + 1) / segs), math.radians(-span * k / segs)
        arcs.append(f'<path d="M{r * math.cos(a1):.1f},{r * math.sin(a1):.1f}A{r:.1f},{r:.1f} 0 0 1 '
                    f'{r * math.cos(a2):.1f},{r * math.sin(a2):.1f}" stroke-width="{2.4 * (1 - k / segs) + .4:.2f}" '
                    f'opacity="{.55 * (1 - k / segs) ** 1.6:.3f}" vector-effect="non-scaling-stroke"/>')
    return (f'<g class="o" {clock(T, p["phase"] * T)} stroke="{colour}" fill="none" '
            f'stroke-linecap="round">{"".join(arcs)}</g>')


def probe_body(name, th):
    ink = th["probe"]
    panel = "#1f6feb" if th["dark"] else "none"
    return (
        f'<rect x="-13" y="-1.6" width="8" height="3.2" fill="{panel}" stroke="{ink}" stroke-width=".6"/>'
        f'<rect x="5" y="-1.6" width="8" height="3.2" fill="{panel}" stroke="{ink}" stroke-width=".6"/>'
        f'<rect x="-3.5" y="-2.5" width="7" height="5" rx="1" fill="{ink}"/>'
        f'<line x1="0" y1="-2.5" x2="0" y2="-7" stroke="{ink}" stroke-width=".7"/>'
        f'<circle cy="-7.5" r="1.4" class="blink" fill="#ff7b72"/>'
    )


def kepler(e, M):
    E = M
    for _ in range(12):
        E -= (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
    return E


def comet(k, name, th):
    """eccentric orbit sampled at equal time steps, so it really does whip
    round the sun and crawl at the far end. Tails always point away from the
    sun, and like the planets it has a front and a back copy so it can pass
    behind the sun instead of over it."""
    rnd = random.Random("comet" + name)
    a, e, w = rnd.uniform(360, 430), 0.62, rnd.uniform(0, 2 * math.pi)
    b = a * math.sqrt(1 - e * e)
    T = rnd.uniform(38, 50)
    n = 120
    pos, tail, near, last = [], [], [], None
    for s in range(n + 1):
        E = kepler(e, 2 * math.pi * s / n)
        x, y = a * (math.cos(E) - e), b * math.sin(E)
        x, y = x * math.cos(w) - y * math.sin(w), (x * math.sin(w) + y * math.cos(w)) * TILT
        ang = math.degrees(math.atan2(y, x))
        if last is not None:
            while ang - last > 180:
                ang -= 360
            while ang - last < -180:
                ang += 360
        last = ang
        pct = f"{100 * s / n:.2f}%"
        pos.append(f"{pct}{{transform:translate({x:.1f}px,{y:.1f}px)}}")
        tail.append(f"{pct}{{transform:rotate({ang:.1f}deg) scale({min(2.4, max(.5, 190 / math.hypot(x, y))):.2f},1)}}")
        near.append(f"{pct}{{opacity:{1 if y > 0 else 0}}}")
    far = [s.replace("opacity:1", "opacity:X").replace("opacity:0", "opacity:1").replace("opacity:X", "opacity:0")
           for s in near]
    css = (f"@keyframes cp{k}{{{''.join(pos)}}}@keyframes ct{k}{{{''.join(tail)}}}"
           f"@keyframes cf{k}{{{''.join(near)}}}@keyframes cb{k}{{{''.join(far)}}}")
    delay = T * (0.9 - 0.3 * k) % T  # the first one is diving at the sun on load
    run = f"{T:.2f}s linear infinite;animation-delay:-{delay:.2f}s"
    head = th["comet"]
    look = (
        f'<g style="animation:ct{k} {run}">'
        + (f'<path d="M0,-1.1L120,0L0,1.1Z" fill="url(#ion)"/>' if th["dark"] else "")
        + f'<path d="M0,-3C30,-3.4 56,-1 82,6L80,9C54,4 28,3.4 0,3Z" fill="url(#tail)"/></g>'
        + (f'<circle r="8" fill="url(#chalo)"/>' if th["dark"] else "")
        + f'<circle r="2.4" fill="{head}"/>'
        + upright(f'<text x="7" y="-8" class="lb sm st">{name}</text>', th)
    )
    copies = {
        side: f'<g style="animation:c{side}{k} {run}"><g style="animation:cp{k} {run}">{look}</g></g>'
        for side in "fb"
    }
    return css, copies


# --- the whole thing -------------------------------------------------------

def keyframes():
    depth = "".join(
        f"{100 * s / 16:.2f}%{{transform:scale({1 + DEPTH * math.sin(2 * math.pi * s / 16):.4f})}}"
        for s in range(17))
    shade, last = [], None
    for s in range(25):
        t = 2 * math.pi * s / 24
        ang = math.degrees(math.atan2(-TILT * math.sin(t), -math.cos(t)))
        if last is not None:
            while ang < last:
                ang += 360
        last = ang
        shade.append(f"{100 * s / 24:.2f}%{{transform:rotate({ang:.2f}deg)}}")
    return f"@keyframes depth{{{depth}}}@keyframes shade{{{''.join(shade)}}}"


def gradients(th):
    ink = th["label"]
    g = [
        '<linearGradient id="shade">'
        f'<stop offset="0" stop-color="{th["shade"]}" stop-opacity=".92"/>'
        f'<stop offset=".4" stop-color="{th["shade"]}" stop-opacity=".7"/>'
        f'<stop offset=".6" stop-color="{th["shade"]}" stop-opacity="0"/></linearGradient>',
        f'<pattern id="hatch" width="2.6" height="2.6" patternUnits="userSpaceOnUse" patternTransform="rotate(35)">'
        f'<line y2="2.6" stroke="{ink}" stroke-width=".75"/></pattern>',
        f'<linearGradient id="tail"><stop offset="0" stop-color="{th["comet"]}" stop-opacity=".8"/>'
        f'<stop offset="1" stop-color="{th["comet"]}" stop-opacity="0"/></linearGradient>',
        '<clipPath id="unit"><circle r="1"/></clipPath>',
    ]
    if th["dark"]:
        g += [
            '<linearGradient id="rim"><stop offset=".55" stop-color="#d7ecff" stop-opacity="0"/>'
            '<stop offset="1" stop-color="#e8f4ff" stop-opacity=".9"/></linearGradient>',
            '<radialGradient id="limb"><stop offset=".55" stop-color="#000" stop-opacity="0"/>'
            '<stop offset=".88" stop-color="#000" stop-opacity=".35"/>'
            '<stop offset="1" stop-color="#000" stop-opacity=".7"/></radialGradient>',
            '<radialGradient id="moon" cx=".38" cy=".35"><stop offset="0" stop-color="#e6ebf1"/>'
            '<stop offset="1" stop-color="#5b636e"/></radialGradient>',
            '<linearGradient id="ion"><stop offset="0" stop-color="#8fc3ff" stop-opacity=".75"/>'
            '<stop offset="1" stop-color="#8fc3ff" stop-opacity="0"/></linearGradient>',
            f'<radialGradient id="chalo"><stop offset="0" stop-color="{th["comet"]}" stop-opacity=".7"/>'
            f'<stop offset="1" stop-color="{th["comet"]}" stop-opacity="0"/></radialGradient>',
            '<radialGradient id="sunglow"><stop offset=".55" stop-color="#fff3c4" stop-opacity=".95"/>'
            '<stop offset=".75" stop-color="#ffc766" stop-opacity=".45"/>'
            '<stop offset="1" stop-color="#ff9a3c" stop-opacity="0"/></radialGradient>'
            '<radialGradient id="sunlimb"><stop offset="0" stop-color="#fff6d8" stop-opacity=".6"/>'
            '<stop offset=".55" stop-color="#ffd27a" stop-opacity="0"/>'
            '<stop offset=".86" stop-color="#ff7a00" stop-opacity=".3"/>'
            '<stop offset="1" stop-color="#a83200" stop-opacity=".85"/></radialGradient>',
            '<radialGradient id="bloom"><stop offset="0" stop-color="#ffd08a" stop-opacity=".5"/>'
            '<stop offset=".2" stop-color="#ff9a3c" stop-opacity=".2"/>'
            '<stop offset=".55" stop-color="#ff7a1a" stop-opacity=".05"/>'
            '<stop offset="1" stop-color="#ff7a1a" stop-opacity="0"/></radialGradient>',
        ]
        for lang, stops in list(RAMP.items()) + [(None, RAMP_OTHER)]:
            g.append(f'<radialGradient id="glow-{lang_key(lang)}"><stop offset=".45" stop-color="{stops[2]}" '
                     f'stop-opacity=".5"/><stop offset="1" stop-color="{stops[1]}" stop-opacity="0"/></radialGradient>')
    else:
        for lang in list(WASH) + [None]:
            g.append(f'<radialGradient id="p-{lang_key(lang)}" cx=".5" cy=".5" r=".55">'
                     f'<stop offset="0" stop-color="#fbf6ea"/><stop offset="1" stop-color="{WASH.get(lang, "#99938a")}"/>'
                     f'</radialGradient>')
        g.append('<radialGradient id="bg" cx=".5" cy=".5" r=".7"><stop offset=".6" stop-color="#f3ead6"/>'
                 '<stop offset="1" stop-color="#e4d4b2"/></radialGradient>'
                 '<radialGradient id="brass" cx=".4" cy=".35"><stop offset="0" stop-color="#f1d9a0"/>'
                 '<stop offset="1" stop-color="#a8834a"/></radialGradient>')
    return "".join(g)


def sky(th, rnd):
    ink, parts = th["label"], []
    if th["dark"]:
        parts.append(f'<image width="{W}" height="{H}" preserveAspectRatio="none" href="{sky_texture()}"/>')
        tints = ("#ffffff", "#ffffff", "#cfe0ff", "#ffe9c9", "#ffd6d6")
        lx, ly = math.cos(math.radians(-24)), math.sin(math.radians(-24))
        for k in range(470):
            if k < 200:  # dust of faint stars crowding the milky way
                t, off = rnd.uniform(-700, 700), rnd.gauss(0, 42)
                x, y = W / 2 + t * lx - off * ly, H * .55 + t * ly + off * lx
                r, op = rnd.uniform(.25, .7), rnd.uniform(.25, .7)
            else:
                x, y = rnd.uniform(0, W), rnd.uniform(0, H)
                r = rnd.uniform(1.3, 1.9) if rnd.random() < .06 else rnd.uniform(.3, 1.15)
                op = rnd.uniform(.3, .95)
            if not (0 <= x <= W and 0 <= y <= H):
                continue
            tw = ""
            if rnd.random() < .28:
                tw = (f' class="tw" style="animation-duration:{rnd.uniform(2, 6):.1f}s;'
                      f'animation-delay:-{rnd.uniform(0, 6):.1f}s"')
            parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.2f}" fill="{rnd.choice(tints)}" '
                         f'opacity="{op:.2f}"{tw}/>')
        for _ in range(6):  # a few bright ones with webb-style spikes
            x, y, s = rnd.uniform(40, W - 40), rnd.uniform(30, H - 30), rnd.uniform(8, 14)
            while math.hypot(x - CX, (y - CY) * 2) < 320:
                x, y = rnd.uniform(40, W - 40), rnd.uniform(30, H - 30)
            spikes = "".join(f'<path d="M0,-.7L{s:.1f},0L0,.7Z" fill="url(#spike)" transform="rotate({a})"/>'
                             for a in (0, 60, 120, 180, 240, 300))
            parts.append(f'<g transform="translate({x:.0f},{y:.0f})">{spikes}<circle r="1.5" fill="#fff"/></g>')
        parts.insert(0, '<defs><linearGradient id="spike"><stop offset="0" stop-color="#fff" stop-opacity=".9"/>'
                        '<stop offset="1" stop-color="#cfe3ff" stop-opacity="0"/></linearGradient></defs>')
    else:
        parts.append(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')
        for _ in range(36):
            x, y, s = rnd.uniform(30, W - 30), rnd.uniform(30, H - 30), rnd.uniform(2, 4.5)
            parts.append(f'<path d="M{x:.0f},{y - s:.1f}L{x + s * .28:.1f},{y:.0f}L{x:.0f},{y + s:.1f}'
                         f'L{x - s * .28:.1f},{y:.0f}ZM{x - s:.1f},{y:.0f}L{x:.0f},{y + s * .28:.1f}'
                         f'L{x + s:.1f},{y:.0f}L{x:.0f},{y - s * .28:.1f}Z" fill="{ink}" opacity=".55"/>')
        ticks = []
        for d in range(0, 360, 5):
            a, ln = math.radians(d), (12 if d % 30 == 0 else 6)
            ticks.append(f'<line x1="{562 * math.cos(a):.1f}" y1="{562 * math.sin(a):.1f}" '
                         f'x2="{(562 + ln) * math.cos(a):.1f}" y2="{(562 + ln) * math.sin(a):.1f}" '
                         f'stroke-width=".7" vector-effect="non-scaling-stroke"/>')
        parts.append(  # graduated rim, like the brass ring on an armillary
            f'<g transform="translate({CX},{CY}) scale(1,{TILT})" stroke="{ink}" fill="none" opacity=".6">'
            f'<circle r="562" stroke-width="1" vector-effect="non-scaling-stroke"/>'
            f'<circle r="574" stroke-width=".6" vector-effect="non-scaling-stroke"/>{"".join(ticks)}</g>')
    return "".join(parts)


def belt(m, th, rnd):
    """rocks ride elliptical paths with SMIL, which moves them without
    squashing them (a spinning, squashed group turns every rock into a dash)"""
    lanes = 7
    T = period(sum(BELT) / 2)
    paths, rocks = [], []
    for k in range(lanes):
        r = BELT[0] + (BELT[1] - BELT[0]) * k / (lanes - 1)
        ry = r * TILT
        paths.append(f'<path id="bl{k}" d="M{r:.1f},0A{r:.1f},{ry:.1f} 0 1 1 {-r:.1f},0'
                     f'A{r:.1f},{ry:.1f} 0 1 1 {r:.1f},0"/>')
    for k in range(len(m["belt"]) + 150):
        big = k < len(m["belt"])  # one proper rock per repo, the rest is gravel
        size = rnd.uniform(1.9, 2.8) if big else rnd.uniform(.5, 1.5)
        op = 1 if big else rnd.uniform(.35, .85)
        lane = rnd.randrange(lanes)
        rocks.append(
            f'<circle cx="{rnd.uniform(-3, 3):.1f}" cy="{rnd.uniform(-2, 2):.1f}" r="{size:.2f}" opacity="{op:.2f}">'
            f'<animateMotion dur="{T * (1 + lane * .015):.1f}s" begin="-{rnd.uniform(0, T):.1f}s" '
            f'repeatCount="indefinite"><mpath href="#bl{lane}"/></animateMotion></circle>')
    dust = ""
    if th["dark"]:
        mid, width = sum(BELT) / 2, BELT[1] - BELT[0]
        dust = (f'<g transform="scale(1,{TILT})" fill="none" stroke="#9fb0c8">'
                + "".join(f'<circle r="{mid:.1f}" stroke-width="{width * f:.1f}" opacity=".014"/>'
                          for f in (2.2, 1.9, 1.6, 1.35, 1.1, .9, .7, .5, .3))
                + "</g>")
    return f'<defs>{"".join(paths)}</defs>{dust}<g fill="{th["belt"]}">{"".join(rocks)}</g>'


def sun(th):
    if not th["dark"]:
        rays = []
        for k in range(24):
            a = math.radians(k * 15)
            L, wd = (46, 6) if k % 2 == 0 else (34, 4.5)
            p1 = (27 * math.cos(a - math.radians(wd)), 27 * math.sin(a - math.radians(wd)))
            p3 = (27 * math.cos(a + math.radians(wd)), 27 * math.sin(a + math.radians(wd)))
            rays.append(f'<path d="M{p1[0]:.1f},{p1[1]:.1f}L{L * math.cos(a):.1f},{L * math.sin(a):.1f}'
                        f'L{p3[0]:.1f},{p3[1]:.1f}Z"/>')
        ink = th["label"]
        return (f'<g transform="translate({CX},{CY})"><g class="o" {clock(160, 0)}>'
                f'<g fill="url(#brass)" stroke="{ink}" stroke-width=".7">{"".join(rays)}</g></g>'
                f'<circle r="27" fill="url(#brass)" stroke="{ink}" stroke-width="1"/>'
                f'<circle r="20" fill="none" stroke="{ink}" stroke-width=".5"/><circle r="3" fill="{ink}"/></g>')
    size = SUN_R * 10
    return (
        f'<defs><image id="corona" x="{-size / 2}" y="{-size / 2}" width="{size}" height="{size}" '
        f'href="{corona_texture()}"/><image id="suntex" width="4" height="2" preserveAspectRatio="none" '
        f'href="{sun_texture()}"/></defs>'
        f'<g transform="translate({CX},{CY})">'
        f'<g class="pulse"><circle r="260" fill="url(#bloom)"/></g>'
        f'<g class="o" {clock(240, 0)}><use href="#corona"/></g>'
        f'<g class="c" {clock(330, 0)} opacity=".55"><use href="#corona" transform="scale(.82) rotate(40)"/></g>'
        f'<circle r="{SUN_R * 1.9}" fill="url(#sunglow)"/>'
        f'<g transform="scale({SUN_R})"><g clip-path="url(#unit)"><g class="roll" style="animation-duration:90s">'
        f'<use href="#suntex" x="-1" y="-1"/><use href="#suntex" x="3" y="-1"/></g></g>'
        f'<circle r="1" fill="url(#sunlimb)"/></g></g>'
    )


def render(m, th):
    rnd = random.Random("sky")
    phi = th["phi"]
    system = f'translate({CX},{CY})' + (f' rotate({phi})' if phi else "")
    defs, extra_css, parts = [gradients(th)], [], []

    parts.append(sky(th, rnd))
    parts.append(f'<g transform="{system}">{belt(m, th, rnd)}</g>')
    ba = math.radians(58)
    bx, by = BELT[1] * math.cos(ba), BELT[1] * TILT * math.sin(ba) + 22
    bx, by = (CX + bx * math.cos(math.radians(phi)) - by * math.sin(math.radians(phi)),
              CY + bx * math.sin(math.radians(phi)) + by * math.cos(math.radians(phi)))
    parts.append(f'<text x="{bx:.0f}" y="{by:.0f}" class="lb sm st">the belt · {len(m["belt"])} more repos</text>')

    # orbits: back halves under the sun, near halves over it; drawn round, then squashed
    radii = [p["r"] for p in m["planets"]] + ([PROBE_R] if m["probe"] else [])
    arcs = {"b": [], "f": []}
    for r in radii:
        arcs["f"].append(f'<path d="M{r:.1f},0A{r:.1f},{r:.1f} 0 0 1 {-r:.1f},0"/>')
        arcs["b"].append(f'<path d="M{-r:.1f},0A{r:.1f},{r:.1f} 0 0 1 {r:.1f},0"/>')

    def orbit_layer(side, op):
        return (f'<g transform="{system} scale(1,{TILT})" fill="none" stroke="{th["orbit"]}" '
                f'opacity="{th["orbit_op"] * op:.2f}">'
                + "".join(a.replace("/>", ' stroke-width=".9" vector-effect="non-scaling-stroke"/>') for a in arcs[side])
                + "</g>")

    parts.append(orbit_layer("b", .7))
    if th["dark"]:
        parts.append(f'<g transform="{system} scale(1,{TILT})">{"".join(trail(p, th) for p in m["planets"])}</g>')

    bodies = []
    for i, p in enumerate(m["planets"]):
        d, draw = planet(p, i, th)
        defs.append(d)
        bodies.append(draw)
    if m["probe"]:
        T, body = period(PROBE_R), probe_body(m["probe"], th)
        bodies.insert(0, lambda layer, T=T, body=body: orbiting(PROBE_R, T, T * .3, body, layer))

    comets = []
    for k, name in enumerate(m["comets"]):
        css, copies = comet(k, name, th)
        extra_css.append(css)
        comets.append(copies)

    back = "".join(b("b") for b in reversed(bodies)) + "".join(c["b"] for c in comets)
    parts.append(f'<g transform="{system}" opacity=".85">{back}</g>')
    parts.append(sun(th))
    parts.append(orbit_layer("f", 1.3))
    front = "".join(b("f") for b in bodies) + "".join(c["f"] for c in comets)
    parts.append(f'<g transform="{system}">{front}</g>')

    if not th["dark"]:
        ink = th["label"]
        parts.append(
            f'<text x="44" y="58" class="title">SYSTEMA SHWETANKIANUM</text>'
            f'<text x="44" y="80" class="lb sub st">orbits after Kepler, drawn from the GitHub API every day</text>'
            f'<text x="{W - 44}" y="{H - 34}" class="lb sub en">Tab. I.</text>'
            f'<rect x="10" y="10" width="{W - 20}" height="{H - 20}" fill="none" stroke="{ink}" stroke-width="2.2"/>'
            f'<rect x="18" y="18" width="{W - 36}" height="{H - 36}" fill="none" stroke="{ink}" stroke-width=".7"/>')

    css = (
        ".o,.c,.d,.s,.pulse{transform-origin:0 0}"
        ".o,.c,.f,.b,.d,.s,.roll{animation-timing-function:linear;animation-iteration-count:infinite}"
        ".o{animation-name:spin}.c{animation-name:unspin}.f{animation-name:front}.b{animation-name:back}"
        ".d{animation-name:depth}.s{animation-name:shade}.roll{animation-name:roll}"
        "@keyframes spin{to{transform:rotate(360deg)}}@keyframes unspin{to{transform:rotate(-360deg)}}"
        "@keyframes front{0%,49.9%{opacity:1}50%,100%{opacity:0}}"
        "@keyframes back{0%,49.9%{opacity:0}50%,100%{opacity:1}}"
        "@keyframes roll{to{transform:translateX(-4px)}}"
        ".tw{animation:tw ease-in-out infinite alternate}@keyframes tw{from{opacity:.1}}"
        ".pulse{animation:pulse 6s ease-in-out infinite alternate}@keyframes pulse{to{transform:scale(1.07)}}"
        ".blink{animation:blink 1.6s steps(1) infinite}@keyframes blink{50%{opacity:.15}}"
        f".lb{{font:{'14px' if th['dark'] else 'italic 15px'} {th['font']};fill:{th['label']};text-anchor:middle;"
        f"paint-order:stroke;stroke:{th['halo']};stroke-width:3.5px;stroke-linejoin:round}}"
        f".sm{{font-size:{'11px' if th['dark'] else '12px'};opacity:.8}}"
        ".sub{font-size:14px}.st{text-anchor:start}.en{text-anchor:end}"
        f".title{{font:600 17px {th['font']};letter-spacing:.32em;fill:{th['label']}}}"
        "@media (prefers-reduced-motion:reduce){*{animation-play-state:paused!important}}"
        + keyframes() + "".join(extra_css)
    )
    names = ", ".join(p["name"] for p in m["planets"])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
        f'aria-label="An animated solar system of shwetank\'s GitHub repos: {names}">'
        f"<title>shwetank's repos as a solar system</title>"
        f'<defs>{"".join(defs)}</defs><style>{css}</style>{"".join(parts)}</svg>'
    )


def main():
    cfg = json.load(open(os.path.join(HERE, "solar.json")))
    m = model(cfg, fetch(cfg["user"]))
    os.makedirs(OUT, exist_ok=True)
    for name, th in (("dark", DARK), ("light", LIGHT)):
        path = os.path.join(OUT, f"solar-{name}.svg")
        with open(path, "w") as f:
            f.write(render(m, th))
        print(f"{path}: {os.path.getsize(path) // 1024} KB")
    print(f"{len(m['planets'])} planets, {len(m['belt'])} in the belt, comets: {', '.join(m['comets']) or 'none'}")


if __name__ == "__main__":
    main()
