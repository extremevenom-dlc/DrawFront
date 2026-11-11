"""
keyboard.py - writes a Windows keyboard-layout source file (.klc) so your own
alphabet can be typed with a real keyboard in any Windows app.

Windows only lets *compiled* layouts appear in its language bar, and compiling one
needs Microsoft's free "Keyboard Layout Creator" (MSKLC). So DrawFont writes the
.klc source; MSKLC turns it into an installer (see README).

Your symbols live in the Unicode private-use area (U+E000...), so they never clash
with real letters. The layout is the normal US keyboard with only your mapped keys
replaced.
"""
import datetime
import re

# (scancode, VK name, character without Shift, character with Shift) - the US layout
_ROWS = [("29", "OEM_3", "`", "~")]
_ROWS += [(f"{0x02 + i:02x}", d, d, s) for i, (d, s) in enumerate(zip("1234567890", "!@#$%^&*()"))]
_ROWS += [("0c", "OEM_MINUS", "-", "_"), ("0d", "OEM_PLUS", "=", "+")]
_ROWS += [(f"{0x10 + i:02x}", c.upper(), c, c.upper()) for i, c in enumerate("qwertyuiop")]
_ROWS += [("1a", "OEM_4", "[", "{"), ("1b", "OEM_6", "]", "}")]
_ROWS += [(f"{0x1e + i:02x}", c.upper(), c, c.upper()) for i, c in enumerate("asdfghjkl")]
_ROWS += [("27", "OEM_1", ";", ":"), ("28", "OEM_7", "'", '"'), ("2b", "OEM_5", "\\", "|")]
_ROWS += [(f"{0x2c + i:02x}", c.upper(), c, c.upper()) for i, c in enumerate("zxcvbnm")]
_ROWS += [("33", "OEM_COMMA", ",", "<"), ("34", "OEM_PERIOD", ".", ">"), ("35", "OEM_2", "/", "?"),
          ("39", "SPACE", " ", " ")]

MAPPABLE = {c for _, _, base, shift in _ROWS for c in (base, shift) if c != " "}


def mappable(key):
    return key in MAPPABLE


def _clean(text):
    return re.sub(r'["\r\n\t]', " ", text).strip()


def build_klc(name, keymap, description=None):
    """Return the text of a .klc file. keymap: {"k": "\\ue000", "K": "\\ue001", ...}."""
    bad = [k for k in keymap if k not in MAPPABLE]
    if bad:
        raise ValueError("These keys can't be used on a standard keyboard: " + " ".join(bad))
    for k, v in keymap.items():
        if len(v) != 1 or ord(v) > 0xFFFF:
            raise ValueError(f"Key {k!r}: the typed symbol must be a single character.")
    short = re.sub(r"[^A-Za-z0-9]", "", name)[:8] or "DrawFont"
    desc = _clean(description or name) or "DrawFont keyboard"
    year = datetime.date.today().year

    rows = []
    for sc, vk, base, shift in _ROWS:
        b, s = keymap.get(base, base), keymap.get(shift, shift)
        mapped = base in keymap or shift in keymap
        cap = 1 if (base.isalpha() and not mapped) else 0
        note = "your symbol" if mapped else f"{vk}"
        rows.append(f"{sc}\t{vk}\t{cap}\t{ord(b):04x}\t{ord(s):04x}\t//{note}")

    lines = [
        f'KBD\t{short}\t"{desc}"', "",
        f'COPYRIGHT\t"(c) {year}"', "",
        'COMPANY\t"DrawFont"', "",
        'LOCALENAME\t"en-US"', "",
        'LOCALEID\t"00000409"', "",
        "VERSION\t1.0", "",
        "SHIFTSTATE", "",
        "0\t//Column 4", "1\t//Column 5 : Shft", "",
        "LAYOUT\t\t;an extra '@' at the end is a dead key", "",
        "//SC\tVK_\t\tCap\t0\t1", "//--\t----\t\t----\t----\t----", "",
        *rows, "",
        "DESCRIPTIONS", "", f"0409\t{desc}", "",
        "LANGUAGENAMES", "", "0409\tEnglish (United States)", "",
        "ENDKBD", "",
    ]
    return "\r\n".join(lines)


def write_klc(path, name, keymap, description=None):
    """MSKLC reads UTF-16 files, so that is what we write."""
    with open(path, "w", encoding="utf-16", newline="") as f:
        f.write(build_klc(name, keymap, description))
