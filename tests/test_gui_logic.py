"""
Drives drawfont.App's real event handlers with a stand-in for Tkinter, so the
GUI logic can be tested on machines with no display (CI, containers).
This does NOT test how it looks - only what happens when you click and draw.
"""
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class Var:
    def __init__(self, master=None, value=None):
        self.v = value

    def get(self):
        return self.v

    def set(self, v):
        self.v = v

    def trace_add(self, *a, **k):
        pass


def install_fake_tk():
    tk = types.ModuleType("tkinter")
    for n in ("StringVar", "IntVar", "BooleanVar"):
        setattr(tk, n, type(n, (Var,), {}))
    for n in ("Tk", "Canvas", "Listbox", "Menu", "Frame", "Label", "Entry"):
        setattr(tk, n, mock.MagicMock(name=n))
    fd, mb, ttk, sd = (types.ModuleType("tkinter." + n) for n in ("filedialog", "messagebox", "ttk", "simpledialog"))
    ttk_mock = mock.MagicMock(name="ttk")
    for n in ("Frame", "Label", "Entry", "Button", "Radiobutton", "Checkbutton",
              "Scale", "Scrollbar", "LabelFrame"):
        setattr(ttk, n, getattr(ttk_mock, n))
    fd.askopenfilename = mock.Mock()
    fd.asksaveasfilename = mock.Mock()
    for n in ("showinfo", "showerror", "askyesnocancel", "askyesno"):
        setattr(mb, n, mock.Mock())
    sd.askstring = mock.Mock()
    tk.filedialog, tk.messagebox, tk.ttk, tk.simpledialog = fd, mb, ttk, sd
    sys.modules.update({"tkinter": tk, "tkinter.filedialog": fd, "tkinter.messagebox": mb,
                        "tkinter.ttk": ttk, "tkinter.simpledialog": sd})
    return tk, fd, mb, sd


TK, FD, MB, SD = install_fake_tk()
import drawfont as df  # noqa: E402
import fontcore as fc  # noqa: E402


def ev(x, y):
    return types.SimpleNamespace(x=x, y=y)


class GuiLogicTests(unittest.TestCase):
    def setUp(self):
        for m in (MB.showinfo, MB.showerror, MB.askyesnocancel, MB.askyesno, SD.askstring,
                  FD.askopenfilename, FD.asksaveasfilename):
            m.reset_mock(return_value=False, side_effect=True)
        self.root = mock.MagicMock()
        self.app = df.App(self.root, project=fc.Project())
        self.app.listbox = mock.MagicMock()
        self.app.tool.set("pen")

    def draw(self, pts):
        self.app._press(ev(*pts[0]))
        for p in pts[1:]:
            self.app._motion(ev(*p))
        self.app._release(ev(*pts[-1]))

    def test_coordinate_roundtrip(self):
        for x, y in ((0, 0), (300, 700), (-20, -150)):
            fx, fy = df.to_font(*df.to_px(x, y))
            self.assertAlmostEqual(fx, x)
            self.assertAlmostEqual(fy, y)

    def test_baseline_is_at_font_y0_and_up_is_positive(self):
        self.draw([(100, df.Y0), (300, df.Y0)])                 # along the baseline
        pts = self.app.project.strokes("A")[0]["pts"]
        self.assertTrue(all(abs(p[1]) < 1e-6 for p in pts))
        self.draw([(100, df.Y0), (100, df.Y0 - 100)])           # drag UP the screen
        self.assertGreater(self.app.project.strokes("A")[1]["pts"][-1][1], 0)

    def test_drawing_creates_stroke_with_pen_width(self):
        self.app.project.settings["pen"] = 64
        self.draw([(100, 100), (150, 160), (220, 200)])
        st = self.app.project.strokes("A")
        self.assertEqual(len(st), 1)
        self.assertEqual(st[0]["w"], 64)
        self.assertEqual(len(st[0]["pts"]), 3)
        self.assertEqual(self.app.live, [])

    def test_tap_makes_a_dot(self):
        self.app.select_char(".")
        self.app._press(ev(200, 300))
        self.app._release(ev(200, 300))
        self.assertEqual(len(self.app.project.strokes(".")), 1)
        self.assertEqual(len(self.app.project.strokes(".")[0]["pts"]), 1)

    def test_pointer_clamped_to_canvas(self):
        self.draw([(-50, -50), (5000, 5000)])
        pts = self.app.project.strokes("A")[0]["pts"]
        fx0, fy0 = pts[0]
        self.assertAlmostEqual(fx0, df.to_font(0, 0)[0], places=1)

    def test_motion_without_press_is_ignored(self):
        self.app._motion(ev(10, 10))
        self.app._release(ev(10, 10))
        self.assertFalse(self.app.project.strokes("A"))

    def test_eraser_removes_only_the_stroke_under_it(self):
        self.draw([(100, 200), (300, 200)])
        self.draw([(100, 400), (300, 400)])
        self.app.tool.set("erase")
        self.app._press(ev(200, 201))
        self.app._release(ev(200, 201))
        self.assertEqual(len(self.app.project.strokes("A")), 1)
        self.assertAlmostEqual(self.app.project.strokes("A")[0]["pts"][0][1], df.to_font(0, 400)[1], delta=0.1)
        self.assertEqual(self.app.live, [])                     # eraser never starts a stroke

    def test_undo_switches_to_the_char_it_restores(self):
        self.draw([(100, 100), (200, 200)])
        self.app.select_char("B")
        self.draw([(100, 100), (200, 200)])
        self.app.undo()
        self.assertEqual(self.app.current, "B")
        self.app.undo()
        self.assertEqual(self.app.current, "A")
        self.assertFalse(self.app.project.strokes("A"))
        self.app.undo()                                         # nothing left: must not crash

    def test_clear_current_only(self):
        self.draw([(100, 100), (200, 200)])
        self.app.select_char("B")
        self.draw([(100, 100), (200, 200)])
        self.app.clear()
        self.assertFalse(self.app.project.strokes("B"))
        self.assertTrue(self.app.project.strokes("A"))

    def test_add_characters(self):
        self.app.add_entry = mock.MagicMock()
        self.app.add_entry.get.return_value = "é অ A"
        self.app.add_chars()
        self.assertIn("é", self.app.project.charset)
        self.assertIn("অ", self.app.project.charset)
        self.assertEqual(self.app.project.charset.count("A"), 1)   # no duplicate
        self.assertEqual(self.app.current, "é")

    def test_settings_apply_and_reflow(self):
        self.draw([(100, 200), (300, 200)])
        a1 = self.app.project.geometry("A")[2]
        self.app.v_side.set(120.4)
        self.app.v_smooth.set(5.0)
        self.app.v_mode.set("fixed")
        self.app._settings_changed()
        s = self.app.project.settings
        self.assertEqual((s["sidebearing"], s["smoothing"], s["spacing"]), (120, 5, "fixed"))
        self.assertEqual(self.app.project.geometry("A")[2], s["fixed_advance"])
        self.assertNotEqual(a1, s["fixed_advance"])

    def test_save_open_roundtrip_through_handlers(self):
        self.draw([(100, 100), (200, 250), (300, 100)])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "p.dfont.json")
            FD.asksaveasfilename.return_value = path
            self.assertTrue(self.app.save_project())
            self.assertFalse(self.app.project.dirty)
            MB.askyesnocancel.return_value = False
            FD.askopenfilename.return_value = path
            self.app.new_project()
            self.assertFalse(self.app.project.strokes("A"))
            self.app.open_project()
            self.assertEqual(len(self.app.project.strokes("A")), 1)
            FD.askopenfilename.return_value = __file__            # not a project file
            self.app.open_project()
            MB.showerror.assert_called_once()

    def test_export_writes_ttf(self):
        self.app.export_font()                                  # nothing drawn
        MB.showinfo.assert_called_once()
        self.draw([(100, 100), (200, 250), (300, 100)])
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "f.ttf")
            FD.asksaveasfilename.return_value = out
            self.app.export_font()
            self.assertTrue(os.path.getsize(out) > 300)
            from fontTools.ttLib import TTFont
            self.assertIn(ord("A"), TTFont(out).getBestCmap())
        MB.showerror.assert_not_called()

    # ---- v2: own alphabet, pictures, keyboard file, updates
    def test_new_symbol_flow(self):
        SD.askstring.side_effect = ["ka", "k"]
        self.app.new_symbol()
        ch = self.app.current
        self.assertEqual(ord(ch), 0xE000)
        self.assertEqual(self.app.project.keymap, {"k": ch})
        self.assertEqual(self.app.project.display_name(ch), "ka")

    def test_new_symbol_cancel_and_bad_key(self):
        SD.askstring.side_effect = [None]
        self.app.new_symbol()
        self.assertFalse(self.app.project.labels)
        SD.askstring.side_effect = ["x", "ab"]
        n = len(self.app.project.charset)
        self.app.new_symbol()
        MB.showerror.assert_called_once()
        self.assertEqual(len(self.app.project.charset), n)

    def test_set_key_for_current(self):
        SD.askstring.side_effect = ["q"]
        self.app.set_key_for_current()
        self.assertEqual(self.app.project.keymap, {"q": "A"})
        SD.askstring.side_effect = [None]            # cancel changes nothing
        self.app.set_key_for_current()
        self.assertEqual(self.app.project.keymap, {"q": "A"})

    def test_export_png_and_klc(self):
        self.draw([(100, 100), (200, 400), (300, 100)])
        self.app.preview_text.set("AA")
        with tempfile.TemporaryDirectory() as d:
            png = os.path.join(d, "t.png")
            FD.asksaveasfilename.return_value = png
            MB.askyesno.return_value = True
            self.app.export_png()
            self.assertGreater(os.path.getsize(png), 100)
            MB.showerror.assert_not_called()

            self.app.export_klc()                                  # no keys yet -> info, no file
            klc = os.path.join(d, "t.klc")
            self.assertFalse(os.path.exists(klc))
            self.app.project.set_key("A", "a")
            FD.asksaveasfilename.return_value = klc
            self.app.export_klc()
            self.assertGreater(os.path.getsize(klc), 500)

    def test_export_png_nothing_drawn_shows_error(self):
        with tempfile.TemporaryDirectory() as d:
            FD.asksaveasfilename.return_value = os.path.join(d, "t.png")
            MB.askyesno.return_value = False
            self.app.export_png()
            MB.showerror.assert_called_once()

    def test_update_branches(self):
        rel = {"version": "99.0.0", "notes": "n", "page": "https://example/page",
               "assets": [{"name": "DrawFont-Setup.exe", "url": "u", "size": 1}]}
        # silent check failing: no popup
        self.app._on_update_result("err", "offline", manual=False)
        MB.showerror.assert_not_called()
        self.app._on_update_result("err", "offline", manual=True)
        MB.showerror.assert_called_once()
        # up to date
        self.app._on_update_result("ok", dict(rel, version="0.0.1"), manual=False)
        MB.askyesno.assert_not_called()
        self.app._on_update_result("ok", None, manual=True)
        MB.showinfo.assert_called()
        # newer, running from source: offers the web page only
        MB.askyesno.return_value = True
        with mock.patch.object(df.webbrowser, "open") as opened, \
                mock.patch.object(self.app, "_download_and_install") as dl:
            self.app._on_update_result("ok", rel, manual=False)
            opened.assert_called_once_with("https://example/page")
            dl.assert_not_called()
        # newer, installed Windows build: downloads and installs
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "platform", "win32"), \
                mock.patch.object(self.app, "_download_and_install") as dl:
            self.app._on_update_result("ok", rel, manual=False)
            dl.assert_called_once_with(rel["assets"][0])
        # user says no: nothing happens
        MB.askyesno.return_value = False
        with mock.patch.object(df.webbrowser, "open") as opened:
            self.app._on_update_result("ok", rel, manual=False)
            opened.assert_not_called()

    def test_downloaded_installer_is_launched_then_app_closes(self):
        with mock.patch.object(df.updater, "run_installer") as run:
            self.app._on_downloaded("ok", "C:/tmp/DrawFont-Setup.exe")
            run.assert_called_once_with("C:/tmp/DrawFont-Setup.exe")
            self.root.destroy.assert_called_once()
        self.root.destroy.reset_mock()
        self.app._on_downloaded("err", "boom")
        MB.showerror.assert_called()
        self.root.destroy.assert_not_called()

    def test_declining_to_save_blocks_update(self):
        self.draw([(100, 100), (200, 200)])                       # unsaved work
        MB.askyesnocancel.return_value = None                     # user cancels
        with mock.patch.object(df.threading, "Thread") as th:
            self.app._download_and_install({"url": "u", "size": 1})
            th.assert_not_called()

    def test_new_projects_default_to_private_use_codes_on_qwerty(self):
        app = df.App(self.root)                                   # no project given -> the default
        app.listbox = mock.MagicMock()
        self.assertTrue(app.project.pua)
        self.assertTrue(app.use_map.get())                        # preview types through the keys
        self.assertEqual(app.current, chr(0xE000))                # first slot = the 'A' key
        app._press(ev(100, 300))
        app._motion(ev(200, 400))
        app._release(ev(200, 400))
        self.assertEqual(len(app.project.strokes(chr(0xE000))), 1)
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "p.ttf")
            FD.asksaveasfilename.return_value = out
            app.export_font()
            from fontTools.ttLib import TTFont
            self.assertEqual(set(TTFont(out).getBestCmap()), {32, 0xE000})   # nothing but your own codes
        app.v_alias.set(True)
        app._settings_changed()
        self.assertTrue(app.project.settings["latin_aliases"])
        app.new_project()
        self.assertTrue(app.project.pua)

    def test_open_a_font_made_on_the_phone(self):
        p = fc.Project.new_pua("Phone Hand")
        p.add_stroke(chr(0xE01A), [(0, 0), (0, 500), (250, 250)], 55)
        with tempfile.TemporaryDirectory() as d:
            ttf = os.path.join(d, "PhoneHand.ttf")
            fc.build_font(p, ttf)
            self.app.project.dirty = False
            FD.askopenfilename.return_value = ttf
            self.app.open_project()
            MB.showerror.assert_not_called()
            self.assertEqual(self.app.project.name, "Phone Hand")
            self.assertEqual(len(self.app.project.strokes(chr(0xE01A))), 1)
            self.assertTrue(self.app.use_map.get())
            self.assertIsNone(self.app.path)                       # a font is not a project file yet
            bad = os.path.join(d, "other.ttf")
            with open(bad, "wb") as f:
                f.write(b"not a font")
            FD.askopenfilename.return_value = bad
            self.app.open_project()
            MB.showerror.assert_called_once()

    def test_quit_respects_unsaved_changes(self):
        self.draw([(100, 100), (200, 200)])
        MB.askyesnocancel.return_value = None                   # user presses Cancel
        self.app.quit()
        self.root.destroy.assert_not_called()
        MB.askyesnocancel.return_value = False                  # "don't save"
        self.app.quit()
        self.root.destroy.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
