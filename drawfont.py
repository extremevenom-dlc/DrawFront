#!/usr/bin/env python3
"""
DrawFont - draw your own letters, get a real font.

Pick a character on the left, draw it with the mouse (or a pen tablet), repeat.
File > Export Font (.ttf) turns every drawing into an installable font whose
letters are exactly the shapes you drew.

Needs Python 3.8+ with Tkinter and the `fonttools` package. See README.md.
"""
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import fontcore as fc

# ---- canvas geometry: font units <-> pixels (y flipped: font y goes up)
SCALE = 0.55
CW, CH = 620, 660
X0 = 50                                  # pixel x of font-unit x = 0
Y0 = int(950 * SCALE)                    # pixel y of the baseline
FILE_TYPES = [("DrawFont project", "*.dfont.json"), ("JSON", "*.json")]

GUIDES = [  # (font y, label, colour)
    (fc.ASCENDER, "ascender", "#d9d9d9"),
    (fc.CAP_HEIGHT, "capital", "#9ec5ff"),
    (fc.X_HEIGHT, "x-height", "#9ec5ff"),
    (0, "baseline", "#ff8a8a"),
    (fc.DESCENDER, "descender", "#d9d9d9"),
]


def to_px(x, y):
    return X0 + x * SCALE, Y0 - y * SCALE


def to_font(px, py):
    return (px - X0) / SCALE, (Y0 - py) / SCALE


class App:
    def __init__(self, root, project=None, path=None):
        self.root = root
        self.project = project or fc.Project()
        self.path = path
        self.current = "A"
        self.tool = tk.StringVar(value="pen")
        self.show_hint = tk.BooleanVar(value=True)
        self.live = []                    # pixel points of the stroke being drawn
        self.live_ids = []
        self.preview_text = tk.StringVar(value="Hello World 123")

        self._build_ui()
        self._refresh_all()
        root.protocol("WM_DELETE_WINDOW", self.quit)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        r = self.root
        r.title("DrawFont")
        r.minsize(980, 760)

        menu = tk.Menu(r)
        fm = tk.Menu(menu, tearoff=0)
        fm.add_command(label="New project", command=self.new_project)
        fm.add_command(label="Open project…", command=self.open_project, accelerator="Ctrl+O")
        fm.add_command(label="Save project", command=self.save_project, accelerator="Ctrl+S")
        fm.add_command(label="Save project as…", command=lambda: self.save_project(True))
        fm.add_separator()
        fm.add_command(label="Export font (.ttf)…", command=self.export_font, accelerator="Ctrl+E")
        fm.add_separator()
        fm.add_command(label="Quit", command=self.quit)
        menu.add_cascade(label="File", menu=fm)
        r.config(menu=menu)
        r.bind("<Control-z>", lambda e: self.undo())
        r.bind("<Control-s>", lambda e: self.save_project())
        r.bind("<Control-o>", lambda e: self.open_project())
        r.bind("<Control-e>", lambda e: self.export_font())

        # left: character list
        left = ttk.Frame(r, padding=8)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Characters  (✓ = drawn)").pack(anchor="w")
        lf = ttk.Frame(left)
        lf.pack(fill="y", expand=True)
        self.listbox = tk.Listbox(lf, width=9, height=30, exportselection=False,
                                  font=("TkDefaultFont", 13), activestyle="none")
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.listbox.yview)
        self.listbox.config(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="y")
        sb.pack(side="left", fill="y")
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        self.add_entry = ttk.Entry(left, width=12)
        self.add_entry.pack(pady=(8, 2), fill="x")
        ttk.Button(left, text="Add characters", command=self.add_chars).pack(fill="x")
        self.add_entry.bind("<Return>", lambda e: self.add_chars())

        # right: tools, drawing canvas, preview, settings
        right = ttk.Frame(r, padding=8)
        right.pack(side="left", fill="both", expand=True)

        bar = ttk.Frame(right)
        bar.pack(fill="x")
        self.title_lbl = ttk.Label(bar, text="", font=("TkDefaultFont", 13, "bold"))
        self.title_lbl.pack(side="left")
        ttk.Button(bar, text="Clear", command=self.clear).pack(side="right")
        ttk.Button(bar, text="Undo (Ctrl+Z)", command=self.undo).pack(side="right", padx=4)
        ttk.Radiobutton(bar, text="Eraser", variable=self.tool, value="erase").pack(side="right", padx=4)
        ttk.Radiobutton(bar, text="Pen", variable=self.tool, value="pen").pack(side="right")

        self.canvas = tk.Canvas(right, width=CW, height=CH, bg="white",
                                highlightthickness=1, highlightbackground="#888", cursor="crosshair")
        self.canvas.pack(pady=6)
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)

        ttk.Label(right, text="Preview — type any text:").pack(anchor="w")
        pe = ttk.Entry(right, textvariable=self.preview_text)
        pe.pack(fill="x")
        self.preview_text.trace_add("write", lambda *a: self._draw_preview())
        self.preview = tk.Canvas(right, width=CW, height=120, bg="white",
                                 highlightthickness=1, highlightbackground="#888")
        self.preview.pack(pady=6, fill="x")

        sf = ttk.LabelFrame(right, text="Font settings", padding=6)
        sf.pack(fill="x")
        s = self.project.settings
        self.v_name = tk.StringVar(value=self.project.name)
        self.v_pen = tk.IntVar(value=s["pen"])
        self.v_smooth = tk.IntVar(value=s["smoothing"])
        self.v_side = tk.IntVar(value=s["sidebearing"])
        self.v_space = tk.IntVar(value=s["space_width"])
        self.v_mode = tk.StringVar(value=s["spacing"])
        self.v_fixed = tk.IntVar(value=s["fixed_advance"])

        def row(i, text, widget):
            ttk.Label(sf, text=text).grid(row=i // 2, column=(i % 2) * 2, sticky="w", padx=4, pady=2)
            widget.grid(row=i // 2, column=(i % 2) * 2 + 1, sticky="ew", padx=4, pady=2)

        row(0, "Font name", ttk.Entry(sf, textvariable=self.v_name, width=22))
        row(1, "Pen thickness", ttk.Scale(sf, from_=10, to=140, variable=self.v_pen, command=self._settings_changed))
        row(2, "Smoothing", ttk.Scale(sf, from_=0, to=8, variable=self.v_smooth, command=self._settings_changed))
        row(3, "Letter gap", ttk.Scale(sf, from_=0, to=150, variable=self.v_side, command=self._settings_changed))
        row(4, "Space width", ttk.Scale(sf, from_=100, to=700, variable=self.v_space, command=self._settings_changed))
        mode = ttk.Frame(sf)
        ttk.Radiobutton(mode, text="Auto spacing", variable=self.v_mode, value="auto",
                        command=self._settings_changed).pack(side="left")
        ttk.Radiobutton(mode, text="Monospace", variable=self.v_mode, value="fixed",
                        command=self._settings_changed).pack(side="left")
        row(5, "Spacing", mode)
        ttk.Checkbutton(sf, text="Show letter hint", variable=self.show_hint,
                        command=self._draw_canvas).grid(row=3, column=0, columnspan=2, sticky="w", padx=4)
        sf.columnconfigure(1, weight=1)
        sf.columnconfigure(3, weight=1)
        self.v_name.trace_add("write", lambda *a: setattr(self.project, "name", self.v_name.get()))

    # ------------------------------------------------------------------ state
    def _settings_changed(self, *_):
        s = self.project.settings
        s["pen"] = int(round(self.v_pen.get()))
        s["smoothing"] = int(round(self.v_smooth.get()))
        s["sidebearing"] = int(round(self.v_side.get()))
        s["space_width"] = int(round(self.v_space.get()))
        s["spacing"] = self.v_mode.get()
        self.project.invalidate()
        self._draw_canvas()
        self._draw_preview()

    def _refresh_all(self):
        self._refresh_list()
        self._draw_canvas()
        self._draw_preview()
        self._update_title()

    def _refresh_list(self):
        self.listbox.delete(0, "end")
        for ch in self.project.charset:
            self.listbox.insert("end", ("✓ " if self.project.strokes(ch) else "   ") + ch)
        if self.current not in self.project.charset and self.project.charset:
            self.current = self.project.charset[0]
        if self.current in self.project.charset:
            i = self.project.charset.index(self.current)
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(i)
            self.listbox.see(i)

    def _update_title(self):
        n = len(self.project.drawn_chars())
        name = os.path.basename(self.path) if self.path else "untitled"
        star = "*" if self.project.dirty else ""
        self.title_lbl.config(text=f"Draw:  {self.current}      ({n} drawn)")
        self.root.title(f"DrawFont — {name}{star}")

    def _on_select(self, _e=None):
        sel = self.listbox.curselection()
        if sel:
            self.current = self.project.charset[sel[0]]
            self._draw_canvas()
            self._update_title()

    def select_char(self, ch):
        self.current = ch
        self._refresh_list()
        self._draw_canvas()

    def add_chars(self):
        added = self.project.add_chars(self.add_entry.get())
        self.add_entry.delete(0, "end")
        if added:
            self.current = added[0]
        self._refresh_all()

    # ------------------------------------------------------------------ drawing
    def _clamp(self, x, y):
        return min(max(x, 0), CW), min(max(y, 0), CH)

    def _press(self, e):
        x, y = self._clamp(e.x, e.y)
        if self.tool.get() == "erase":
            self._erase_at(x, y)
            return
        self.live = [(x, y)]
        self.live_ids = []

    def _motion(self, e):
        x, y = self._clamp(e.x, e.y)
        if self.tool.get() == "erase":
            self._erase_at(x, y)
            return
        if not self.live:
            return
        lx, ly = self.live[-1]
        if (x - lx) ** 2 + (y - ly) ** 2 < 4:      # ignore sub-2px jitter
            return
        w = self.project.settings["pen"] * SCALE
        self.live_ids.append(self.canvas.create_line(lx, ly, x, y, width=w, capstyle="round",
                                                     fill="#222", tags="live"))
        self.live.append((x, y))

    def _release(self, _e=None):
        if not self.live:
            return
        pts = [to_font(px, py) for px, py in self.live]
        self.live = []
        self.canvas.delete("live")
        self.project.add_stroke(self.current, pts, self.project.settings["pen"])
        self._after_edit()

    def _erase_at(self, px, py):
        x, y = to_font(px, py)
        if self.project.erase_near(self.current, x, y, 12 / SCALE):
            self._after_edit()

    def undo(self):
        ch = self.project.undo()
        if ch is None:
            return
        if ch != self.current:
            self.current = ch
            self._refresh_list()
        self._after_edit()

    def clear(self):
        self.project.clear(self.current)
        self._after_edit()

    def _after_edit(self):
        self._draw_canvas()
        self._draw_preview()
        self._refresh_list()
        self._update_title()

    # ------------------------------------------------------------------ rendering
    def _draw_canvas(self):
        c = self.canvas
        c.delete("all")
        for gy, label, col in GUIDES:
            _, py = to_px(0, gy)
            c.create_line(0, py, CW, py, fill=col, dash=(4, 3))
            c.create_text(CW - 4, py - 7, text=label, anchor="e", fill=col, font=("TkDefaultFont", 8))
        if self.show_hint.get() and self.current.strip():
            _, base = to_px(0, 0)
            c.create_text(CW / 2, base - fc.CAP_HEIGHT * SCALE / 2, text=self.current,
                          fill="#ececec", font=("TkDefaultFont", int(fc.CAP_HEIGHT * SCALE * 0.7)))
        g = self.project.geometry(self.current)
        if g:
            for poly in g[0]:
                flat = [v for pt in poly for v in to_px(*pt)]
                c.create_polygon(flat, fill="#222", outline="#222")

    def _draw_preview(self):
        c = self.preview
        c.delete("all")
        text = self.preview_text.get()
        polys, adv = self.project.layout(text)
        w = max(int(c.winfo_width()), 200)
        h = max(int(c.winfo_height()), 100)
        if adv <= 0:
            return
        k = min((h - 24) / 1000.0, (w - 24) / adv)
        base = 12 + fc.ASCENDER * k
        for poly in polys:
            flat = []
            for x, y in poly:
                flat += [12 + x * k, base - y * k]
            c.create_polygon(flat, fill="#222", outline="#222")

    # ------------------------------------------------------------------ files
    def _confirm_discard(self):
        if not self.project.dirty:
            return True
        ans = messagebox.askyesnocancel("Unsaved changes", "Save your project first?")
        if ans is None:
            return False
        if ans:
            return self.save_project()
        return True

    def new_project(self):
        if self._confirm_discard():
            self._load(fc.Project(), None)

    def open_project(self):
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(filetypes=FILE_TYPES + [("All files", "*.*")])
        if not path:
            return
        try:
            self._load(fc.Project.load(path), path)
        except Exception as ex:                      # corrupt file, wrong format, ...
            messagebox.showerror("Could not open", str(ex))

    def _load(self, project, path):
        self.project, self.path = project, path
        s = project.settings
        self.v_name.set(project.name)
        self.v_pen.set(s["pen"])
        self.v_smooth.set(s["smoothing"])
        self.v_side.set(s["sidebearing"])
        self.v_space.set(s["space_width"])
        self.v_mode.set(s["spacing"])
        self.current = project.charset[0] if project.charset else "A"
        self._refresh_all()

    def save_project(self, save_as=False):
        path = self.path
        if save_as or not path:
            path = filedialog.asksaveasfilename(defaultextension=".dfont.json", filetypes=FILE_TYPES,
                                                initialfile=(self.project.name or "MyHandwriting") + ".dfont.json")
        if not path:
            return False
        try:
            self.project.save(path)
        except OSError as ex:
            messagebox.showerror("Could not save", str(ex))
            return False
        self.path = path
        self._update_title()
        return True

    def export_font(self):
        if not self.project.drawn_chars():
            messagebox.showinfo("Nothing to export", "Draw at least one character first.")
            return
        name = (self.project.name or "MyHandwriting").strip()
        path = filedialog.asksaveasfilename(defaultextension=".ttf", filetypes=[("TrueType font", "*.ttf")],
                                            initialfile=name.replace(" ", "") + ".ttf")
        if not path:
            return
        try:
            info = fc.build_font(self.project, path)
        except Exception as ex:
            messagebox.showerror("Export failed", str(ex))
            return
        messagebox.showinfo(
            "Font exported",
            f"Saved {info['glyphs']} characters as “{info['family']}”:\n{path}\n\n"
            "To use it: double-click the .ttf file and press Install "
            "(Windows / macOS), or copy it to ~/.fonts on Linux. "
            "Restart apps like Word or Photoshop afterwards.")

    def quit(self):
        if self._confirm_discard():
            self.root.destroy()


def main():
    root = tk.Tk()
    app = App(root)
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):       # drawfont.py myfont.dfont.json
        try:
            app._load(fc.Project.load(sys.argv[1]), sys.argv[1])
        except Exception as ex:
            messagebox.showerror("Could not open", str(ex))
    root.mainloop()


if __name__ == "__main__":
    main()
