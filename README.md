# DrawFont — draw your letters, get a real font

A free desktop app. You draw each character with your mouse (or a pen tablet),
and DrawFont turns your drawings into an installable `.ttf` font. The letters in
the font are the shapes you drew — nothing is generated or guessed.

- Draw any character: A–Z, a–z, 0–9, punctuation, or add your own (é, ñ, অ, …)
- Live preview: type any text and see it in your handwriting as you go
- Pen thickness, smoothing, letter gap, space width, auto or monospace spacing
- Undo, eraser (removes the stroke you touch), clear
- Save/open projects, so you can finish your alphabet over several days
- Export a standard TrueType font for Windows, macOS and Linux

---

## Part 1 — Put it on GitHub (one time, about 5 minutes)

1. Create a free account at <https://github.com> if you don't have one.
2. Click **+** (top right) → **New repository**. Name it `drawfont`, choose **Public**, and click **Create repository**.
3. On the new empty repository page click **uploading an existing file**.
4. Unzip `drawfont.zip` on your computer, then drag **everything inside the `drawfont` folder** into the browser window.
   Include the hidden `.github` folder: if your file manager hides it, turn on "show hidden files" first
   (Windows: View → Show → Hidden items; macOS: press `Cmd + Shift + .`).
5. Click **Commit changes**.

## Part 2 — Get a double-click app (no Python needed)

GitHub can build the app for you, free:

1. In your repository click **Releases** (right side) → **Create a new release**.
2. In **Choose a tag** type `v1.0`, pick **Create new tag**, then click **Publish release**.
3. Click the **Actions** tab and wait about 5 minutes for **Build apps** to finish (green tick).
4. Go back to **Releases** → `v1.0`. Under **Assets** download:
   - `DrawFont-Windows.exe` — Windows
   - `DrawFont-macOS.zip` — macOS (unzip it; first launch: right-click → **Open**)
   - `DrawFont-Linux` — Linux (`chmod +x DrawFont-Linux && ./DrawFont-Linux`)

Windows may show "Windows protected your PC" because the app isn't code-signed:
click **More info → Run anyway**.

## Part 3 — Or run from source (works right away)

You need **Python 3.8 or newer** with Tkinter.

| System | Install Python |
|---|---|
| Windows | <https://www.python.org/downloads/> — Tkinter is included. Tick **Add python.exe to PATH**. |
| macOS | <https://www.python.org/downloads/> (the python.org installer includes Tkinter). With Homebrew: `brew install python-tk`. |
| Linux | `sudo apt install python3 python3-tk python3-pip` (Debian/Ubuntu) |

Download the code: on your repository page click **Code → Download ZIP** and unzip it
(or `git clone https://github.com/YOUR-NAME/drawfont.git`). Then open a terminal in that folder:

```
pip install -r requirements.txt
python drawfont.py
```

On Windows use `py` instead of `python` if `python` isn't found. On Linux/macOS use `python3` and `pip3`.

## Part 4 — Make your font

1. Click a character in the left list (start with `A`).
2. Draw it in the big box. Sit capitals between the **capital** and **baseline** lines,
   lowercase letters between **x-height** and **baseline**; letters like g, j, p, q, y can drop below the baseline.
   Position and size matter — what you see is where the letter sits in the font.
3. Made a mistake? **Ctrl+Z** undoes the last stroke, **Eraser** deletes the stroke you touch, **Clear** wipes the character.
4. For a dot (i, j, `.`), just click once.
5. Move on to the next character. A ✓ appears next to every character you have drawn.
   Type any text in **Preview** to check how words look and adjust **Letter gap**, **Space width** and **Smoothing**.
6. **File → Save project** (so you can continue later) and **File → Export font (.ttf)**.
7. Install the font:
   - **Windows:** double-click the `.ttf` → **Install**.
   - **macOS:** double-click the `.ttf` → **Install Font**.
   - **Linux:** copy it into `~/.fonts` (or `~/.local/share/fonts`) and run `fc-cache -f`.
   Restart Word / Photoshop / Canva / etc. and pick your font name.

Characters you didn't draw simply won't exist in the font (your computer falls back to another font for them).

## Tips

- **Smoothing 0** keeps your mouse path exactly; 2–3 removes hand-shake without changing the letter's shape.
- Draw big and steady rather than small; strokes are stored precisely, so a font made from a trackpad is as good as your drawing.
- Letters that touch themselves (like an `8` or `A` crossbar) work fine — overlapping strokes merge into one solid shape.
- The font uses a single pen thickness per stroke. You can change the thickness between strokes.

## Known limits

- Fonts are made from pen strokes (like a marker), not filled outlines drawn by hand — to draw an outline shape, trace it with a thick pen.
- One style (Regular). No kerning pairs or ligatures; use **Letter gap** for spacing.
- Rounding: outlines are stored as straight segments at 1000 units per em (about 0.1% precision) — far below visible at normal sizes.

## Development

```
pip install -r requirements.txt pillow
python -m unittest discover -s tests      # 30 tests, no display needed
```

`fontcore.py` is the font engine (no GUI, fully tested); `drawfont.py` is the Tkinter window.

## License

MIT — free for personal and commercial use. Fonts you make are yours.
