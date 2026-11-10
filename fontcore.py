"""
fontcore.py - turns hand-drawn strokes into a real, installable TrueType font.

There is no GUI code in this file, so all of it can be tested without a screen.

Coordinates everywhere are font units with the y axis pointing UP:
    baseline = 0, 1000 units per em, ascender 800, descender -200.

How "exact" works: nothing is guessed or generated. Every stroke you draw is kept
as a list of points plus a pen width. The font outline is the shape a round pen
of that width leaves when it follows those points - the same shape the app shows
on screen while you draw.
"""
from __future__ import annotations

import json
import math
import string

from fontTools.agl import UV2AGL
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

# --------------------------------------------------------------------------- constants

UPM = 1000
ASCENDER = 800
DESCENDER = -200
CAP_HEIGHT = 700
X_HEIGHT = 500

DEFAULT_CHARSET = (
    string.ascii_uppercase
    + string.ascii_lowercase
    + string.digits
    + ".,!?;:'\"-_()[]{}&@#$%*+=/\\<>|~^`"
)

DEFAULT_SETTINGS = {
    "smoothing": 2,        # 0 = raw mouse path, higher = smoother (0..8)
    "pen": 50,             # pen width in font units for NEW strokes
    "sidebearing": 40,     # space left/right of each letter ("auto" spacing)
    "spacing": "auto",     # "auto" = fit to ink, "fixed" = monospace
    "fixed_advance": 600,  # letter width for "fixed" spacing
    "space_width": 300,    # width of the space character
}

PROJECT_FORMAT = "drawfont-project"
PROJECT_VERSION = 1

_RDP_EPS = 1.2            # simplification tolerance in font units (invisible at 1000 upm)
_JOIN_COS = math.cos(math.radians(25))  # turns sharper than 25 degrees get a round join
_UNDO_LIMIT = 300
_OVERLAP = 1.5            # units each segment extends past its ends (hides rounding seams)


# --------------------------------------------------------------------------- stroke geometry

def _dedupe(pts, min_dist=0.5):
    out = []
    for x, y in pts:
        if not out or math.hypot(x - out[-1][0], y - out[-1][1]) >= min_dist:
            out.append((x, y))
    return out


def _smooth(pts, passes):
    """Light [1 2 1]/4 smoothing; endpoints stay fixed so strokes start/end where you put them."""
    for _ in range(max(0, int(passes))):
        if len(pts) < 3:
            break
        new = [pts[0]]
        for i in range(1, len(pts) - 1):
            new.append((
                (pts[i - 1][0] + 2 * pts[i][0] + pts[i + 1][0]) / 4.0,
                (pts[i - 1][1] + 2 * pts[i][1] + pts[i + 1][1]) / 4.0,
            ))
        new.append(pts[-1])
        pts = new
    return pts


def _rdp(pts, eps):
    """Ramer-Douglas-Peucker simplification (iterative, so long strokes can't overflow the stack)."""
    n = len(pts)
    if n < 3:
        return pts
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        best, best_i = -1.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            if seg2 == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
                d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
            if d > best:
                best, best_i = d, i
        if best > eps:
            keep[best_i] = True
            stack.append((a, best_i))
            stack.append((best_i, b))
    return [p for p, k in zip(pts, keep) if k]


def clean_points(pts, smoothing):
    pts = _dedupe([(float(x), float(y)) for x, y in pts])
    if len(pts) < 3:
        return pts
    pts = _smooth(pts, smoothing)
    return _rdp(pts, _RDP_EPS)


def _area(poly):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1])) / 2.0


def _cw(poly):
    """TrueType wants outer contours clockwise (y up => negative signed area)."""
    return poly[::-1] if _area(poly) > 0 else poly


def _circle(cx, cy, r):
    n = 12 if r < 30 else 16 if r < 60 else 24
    return [(cx + r * math.cos(-2 * math.pi * k / n), cy + r * math.sin(-2 * math.pi * k / n))
            for k in range(n)]


def stroke_polygons(pts, width, smoothing=2):
    """
    Outline of a round pen of `width` following `pts`, as a list of clockwise polygons.
    The polygons overlap each other; TrueType fills overlapping same-direction
    contours as one solid shape (non-zero winding), so no boolean union is needed.
    """
    r = width / 2.0
    pts = clean_points(pts, smoothing)
    if not pts:
        return []
    if len(pts) == 1:                      # a tap = a dot (i-dots, full stops)
        return [_circle(pts[0][0], pts[0][1], r)]

    polys = [_circle(pts[0][0], pts[0][1], r), _circle(pts[-1][0], pts[-1][1], r)]
    dirs = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)        # > 0 because of _dedupe
        ux, uy = dx / length, dy / length
        dirs.append((ux, uy))
        nx, ny = -uy * r, ux * r
        # Overlap neighbours by _OVERLAP units: font coordinates are rounded to
        # integers, and exactly-abutting edges can round apart into hairline seams.
        ex, ey = ux * _OVERLAP, uy * _OVERLAP
        polys.append(_cw([(x0 - ex + nx, y0 - ey + ny), (x1 + ex + nx, y1 + ey + ny),
                          (x1 + ex - nx, y1 + ey - ny), (x0 - ex - nx, y0 - ey - ny)]))

    for i in range(1, len(pts) - 1):       # fill the gap on the outside of every bend
        (u1x, u1y), (u2x, u2y) = dirs[i - 1], dirs[i]
        cross = u1x * u2y - u1y * u2x
        dot = u1x * u2x + u1y * u2y
        if abs(cross) < 1e-6 and dot > 0:
            continue
        px, py = pts[i]
        if dot < _JOIN_COS:
            polys.append(_circle(px, py, r))
            continue
        s = -1.0 if cross > 0 else 1.0     # outer side of the turn
        polys.append(_cw([(px, py),
                          (px - u1y * r * s, py + u1x * r * s),
                          (px - u2y * r * s, py + u2x * r * s)]))
    return polys


def glyph_polygons(strokes, smoothing=2):
    polys = []
    for st in strokes:
        polys.extend(stroke_polygons(st["pts"], st["w"], smoothing))
    return polys


def bounds(polys):
    xs = [x for p in polys for x, _ in p]
    ys = [y for p in polys for _, y in p]
    return min(xs), min(ys), max(xs), max(ys)


def place(polys, settings):
    """Return (dx, advance): how far to shift the drawing sideways, and the letter's width."""
    minx, _, maxx, _ = bounds(polys)
    if settings["spacing"] == "fixed":
        adv = float(settings["fixed_advance"])
        return adv / 2.0 - (minx + maxx) / 2.0, adv
    sb = float(settings["sidebearing"])
    return sb - minx, (maxx - minx) + 2 * sb


def shift(polys, dx):
    return [[(x + dx, y) for x, y in p] for p in polys]


# --------------------------------------------------------------------------- project

class Project:
    """All the user's drawings plus settings. Saves/loads as a plain JSON file."""

    def __init__(self, name="MyHandwriting"):
        self.name = name
        self.settings = dict(DEFAULT_SETTINGS)
        self.charset = list(DEFAULT_CHARSET)
        self.glyphs = {}          # char -> [ {"w": width, "pts": [[x, y], ...]}, ... ]
        self._undo = []           # [(char, snapshot of that char's strokes)]
        self._cache = {}
        self.dirty = False

    # ---- bookkeeping
    def _touch(self, ch):
        self._cache.pop(ch, None)
        self.dirty = True

    def invalidate(self):
        """Call after changing smoothing/spacing settings."""
        self._cache.clear()
        self.dirty = True

    def strokes(self, ch):
        return self.glyphs.get(ch, [])

    def drawn_chars(self):
        seen = list(self.charset) + [c for c in self.glyphs if c not in self.charset]
        return [c for c in seen if self.glyphs.get(c)]

    def add_chars(self, text):
        added = []
        for ch in text:
            if ch.isspace() or ch in self.charset:
                continue
            self.charset.append(ch)
            added.append(ch)
        if added:
            self.dirty = True
        return added

    # ---- editing (each edit is undoable)
    def _snapshot(self, ch):
        self._undo.append((ch, json.loads(json.dumps(self.glyphs.get(ch, [])))))
        del self._undo[:-_UNDO_LIMIT]

    def add_stroke(self, ch, pts, width):
        if not pts:
            return
        self._snapshot(ch)
        self.glyphs.setdefault(ch, []).append(
            {"w": float(width), "pts": [[round(x, 1), round(y, 1)] for x, y in pts]})
        self._touch(ch)

    def clear(self, ch):
        if self.glyphs.get(ch):
            self._snapshot(ch)
            self.glyphs[ch] = []
            self._touch(ch)

    def erase_near(self, ch, x, y, radius):
        """Remove every stroke of `ch` passing within `radius` of (x, y). True if any removed."""
        keep, hit = [], False
        for st in self.glyphs.get(ch, []):
            if _dist_to_polyline(x, y, st["pts"]) <= radius + st["w"] / 2.0:
                hit = True
            else:
                keep.append(st)
        if hit:
            self._snapshot(ch)
            self.glyphs[ch] = keep
            self._touch(ch)
        return hit

    def undo(self):
        """Undo the last edit anywhere. Returns the character that was restored, or None."""
        if not self._undo:
            return None
        ch, strokes = self._undo.pop()
        self.glyphs[ch] = strokes
        self._touch(ch)
        return ch

    # ---- geometry
    def _sig(self):
        s = self.settings
        return (s["smoothing"], s["sidebearing"], s["spacing"], s["fixed_advance"])

    def geometry(self, ch):
        """(polygons as drawn, dx to apply when placed in the font, advance width) or None."""
        hit = self._cache.get(ch)
        if hit and hit[0] == self._sig():
            return hit[1]
        strokes = self.glyphs.get(ch)
        if not strokes:
            return None
        polys = glyph_polygons(strokes, self.settings["smoothing"])
        if not polys:
            return None
        dx, adv = place(polys, self.settings)
        val = (polys, dx, adv)
        self._cache[ch] = (self._sig(), val)
        return val

    def layout(self, text):
        """Lay out text with the drawn glyphs: (polygons in line space, total advance)."""
        out, pen_x = [], 0.0
        for ch in text:
            if ch == " ":
                pen_x += self.settings["space_width"]
                continue
            g = self.geometry(ch)
            if g is None:
                pen_x += 500          # not drawn yet: leave a gap
                continue
            polys, dx, adv = g
            out.extend(shift(polys, dx + pen_x))
            pen_x += adv
        return out, pen_x

    # ---- save / load
    def to_dict(self):
        return {
            "format": PROJECT_FORMAT, "version": PROJECT_VERSION, "name": self.name,
            "settings": self.settings, "charset": "".join(self.charset),
            "glyphs": {c: s for c, s in self.glyphs.items() if s},
        }

    @classmethod
    def from_dict(cls, d):
        if not isinstance(d, dict) or d.get("format") != PROJECT_FORMAT:
            raise ValueError("This is not a DrawFont project file.")
        p = cls(str(d.get("name") or "MyHandwriting"))
        p.settings.update({k: v for k, v in (d.get("settings") or {}).items() if k in DEFAULT_SETTINGS})
        if d.get("charset"):
            p.charset = list(dict.fromkeys(d["charset"]))
        for ch, strokes in (d.get("glyphs") or {}).items():
            clean = []
            for st in strokes:
                pts = [[float(x), float(y)] for x, y in st["pts"]]
                if pts:
                    clean.append({"w": float(st["w"]), "pts": pts})
            if clean:
                p.glyphs[ch] = clean
        p.dirty = False
        return p

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f)
        self.dirty = False

    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


def _dist_to_polyline(px, py, pts):
    if len(pts) == 1:
        return math.hypot(px - pts[0][0], py - pts[0][1])
    best = float("inf")
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        t = 0.0 if seg2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
        best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
    return best


# --------------------------------------------------------------------------- font export

def glyph_name(cp):
    return UV2AGL.get(cp) or (f"uni{cp:04X}" if cp <= 0xFFFF else f"u{cp:X}")


def _ps_name(name):
    clean = "".join(c for c in name if c.isascii() and c.isalnum())
    return (clean or "DrawFont") + "-Regular"


def _pen_glyph(polys):
    pen = TTGlyphPen(None)
    for poly in polys:
        pen.moveTo(poly[0])
        for pt in poly[1:]:
            pen.lineTo(pt)
        pen.closePath()
    return pen.glyph()


def build_font(project, path):
    """Write `project` to a .ttf file at `path`. Returns a small summary dict."""
    chars = [c for c in project.drawn_chars() if c != " "]
    if not chars:
        raise ValueError("Draw at least one character before exporting.")

    notdef = _pen_glyph([
        [(50, 0), (50, 700), (450, 700), (450, 0)],                 # outer box (clockwise)
        [(100, 50), (400, 50), (400, 650), (100, 650)],             # inner hole (counter-clockwise)
    ])
    glyphs = {".notdef": notdef, "space": TTGlyphPen(None).glyph()}
    advances = {".notdef": 500, "space": int(project.settings["space_width"])}
    cmap = {32: "space"}
    order = [".notdef", "space"]
    ymin, ymax = DESCENDER, ASCENDER

    for ch in chars:
        polys, dx, adv = project.geometry(ch)
        name = glyph_name(ord(ch))
        placed = shift(polys, dx)
        _, gy0, _, gy1 = bounds(placed)
        ymin, ymax = min(ymin, gy0), max(ymax, gy1)
        glyphs[name] = _pen_glyph(placed)
        advances[name] = int(round(adv))
        cmap[ord(ch)] = name
        order.append(name)

    family = project.name.strip() or "MyHandwriting"
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)

    glyf = fb.font["glyf"]
    metrics = {}
    for name in order:
        g = glyf[name]
        metrics[name] = (advances[name], getattr(g, "xMin", 0) if g.numberOfContours else 0)
        if g.numberOfContours > 0 and len(g.flags):
            g.flags[0] |= 0x40                      # OVERLAP_SIMPLE: tells macOS to fill overlaps
    fb.setupHorizontalMetrics(metrics)

    top, bottom = int(math.ceil(ymax)), int(math.floor(ymin))
    fb.setupHorizontalHeader(ascent=top, descent=bottom)
    fb.setupNameTable({
        "familyName": family, "styleName": "Regular",
        "uniqueFontIdentifier": f"DrawFont: {family}",
        "fullName": family, "psName": _ps_name(family), "version": "Version 1.000",
    })
    fb.setupOS2(sTypoAscender=ASCENDER, sTypoDescender=DESCENDER, sTypoLineGap=0,
                usWinAscent=top, usWinDescent=-bottom, sxHeight=X_HEIGHT,
                sCapHeight=CAP_HEIGHT, usWeightClass=400, achVendID="DRWF", fsType=0)
    fb.setupPost()
    fb.save(path)
    return {"glyphs": len(chars), "path": path, "family": family}
