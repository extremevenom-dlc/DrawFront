"""The Android app (Kotlin) hands the project to Python as JSON. This checks that exact handoff,
using JSON shaped like Project.toJson() in android/.../Project.kt."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "android", "app", "src", "main", "python"))

import bridge  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402

# Same keys/types org.json produces in Project.toJson(): ints for settings, doubles for points,
# labels/keymap as objects, charset as one string, private-use chars inside JSON strings.
KOTLIN_JSON = json.dumps({
    "format": "drawfont-project", "version": 1, "name": "Phone Hand",
    "settings": {"smoothing": 2, "pen": 55, "sidebearing": 40, "spacing": "auto",
                 "fixed_advance": 600, "space_width": 300},
    "charset": "AB",
    "glyphs": {
        "A": [{"w": 55.0, "pts": [[0.0, 0.0], [150.5, 700.0], [300.0, 0.0]]}],
        "": [{"w": 55.0, "pts": [[10.0, 10.0]]}],
    },
    "labels": {"": "ka"}, "keymap": {"k": ""},
})


class BridgeTests(unittest.TestCase):
    def test_kotlin_json_builds_a_font(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "Phone.ttf")
            n = bridge.build(KOTLIN_JSON, out)
            self.assertEqual(n, 2)
            f = TTFont(out)
            cmap = f.getBestCmap()
            self.assertIn(ord("A"), cmap)
            self.assertIn(0xE000, cmap)
            self.assertEqual(f["name"].getDebugName(1), "Phone Hand")

    def test_bad_json_raises_instead_of_crashing_silently(self):
        with self.assertRaises(Exception):
            bridge.build("{}", "/tmp/never.ttf")


if __name__ == "__main__":
    unittest.main(verbosity=2)
