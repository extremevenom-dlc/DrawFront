# DrawFont — draw your own alphabet, type with it

Free apps for **Windows** and **Android**. You draw every letter with a mouse, pen or finger.
DrawFont turns your drawings into an installable `.ttf` font **and** a QWERTY keyboard layout, so you can
type in your own alphabet. The letters in the font are exactly the shapes you drew.

- **Your own alphabet, on private-use codes.** Every character you draw is stored at its own code in the
  Unicode *Private Use Area* (U+E000 and up), so it never clashes with real letters or other fonts.
- **Standard QWERTY keys.** Each key of a normal US keyboard types its slot: press `a`, get your drawn "a".
- **Windows:** installer, automatic updates, undo/eraser, live preview, export font / picture / keyboard layout.
- **Android:** same drawing and font export, plus a "Type & share" screen that sends your handwriting as a picture.
- **Draw once, use everywhere:** the exported `.ttf` carries your editable drawings inside it. Draw on your phone, send yourself
  the `.ttf`, and on your PC you can install it **and** open it in DrawFont to keep editing — no redrawing.

> Not a registered "language": Windows only lists officially registered languages, so an app can't add a brand-new
> entry like *Bangla (Bangladesh)*. A keyboard layout with your own alphabet (what DrawFont makes) is the real way.

---

## 1. Get the apps (after you publish a release — see section 6)

On your GitHub repository open **Releases → latest** and download:

| File | For |
|---|---|
| `DrawFont-Setup.exe` | **Windows** installer (recommended; updates itself) |
| `DrawFont-Windows-portable.exe` | Windows, no install |
| `DrawFont-Android.apk` | **Android** phones and tablets |

Share the Releases link with friends on WhatsApp or Discord. It's the only thing they need to install the apps.

**Windows:** run the installer. If it says "Windows protected your PC", click **More info → Run anyway** (the app is not code-signed).
**Android:** open the `.apk` on your phone and allow "install unknown apps" when asked. Google Play Protect may show a warning for apps outside the Play Store; choose "Install anyway".

## 2. Draw your alphabet

1. Pick a slot on the left. New projects start with all 94 keys of a US keyboard: A–Z, a–z, 0–9 and punctuation.
2. Draw it between the guide lines (capitals: *capital* to *baseline*; lowercase: *x-height* to *baseline*; g, j, p, q, y may drop below).
3. **Undo**, **Eraser** (deletes the stroke you touch) and **Clear** fix mistakes. Tap once for a dot.
4. Need more than 94 characters? **Alphabet → New custom symbol** (Windows) or **+ Symbol** (Android) makes a new slot.
   Extra characters you type into "Add characters" also become new private-use slots.
5. **File → Save project** often. **File → Export font (.ttf)** when you are done.

### The code table (never changes, so projects from any device line up)

| Keys | Codes |
|---|---|
| `A` … `Z` | U+E000 … U+E019 |
| `a` … `z` | U+E01A … U+E033 |
| `0` … `9` | U+E034 … U+E03D |
| `. , ! ? ; : ' " - _ ( ) [ ] { } & @ # $ % * + = / \ < > \| ~ ^` and backtick | U+E03E … U+E05D |
| extra symbols you add | U+E05E and up (to U+F8FF) |

The space bar stays a normal space.

## 3. Use it on Windows

1. **Install the font:** double-click the exported `.ttf` → **Install**. Restart Word etc. and pick the font.
2. **Typing:** because every letter is a private-use character, a normal keyboard would type normal letters. Two options:
   - **Easiest:** tick **"Also make normal keys show my letters"** in the font settings before exporting. Typing `a` then shows your "a" in any app using the font. (The font then contains both the private-use code and the plain key.)
   - **Real keyboard layout (your own entry in the Windows language bar):** **File → Export Windows keyboard layout (.klc)**, then
     1. install Microsoft's free **Keyboard Layout Creator (MSKLC)**,
     2. open the `.klc` in it → **Project → Build DLL and Setup Package**,
     3. run the `setup.exe` it creates, then add the keyboard in **Settings → Time & language → Language & region → English (United States) → Options → Add a keyboard**,
     4. switch to it with Win+Space and type: standard QWERTY keys produce your letters.
   The layout is the normal US QWERTY layout; only the 94 typeable characters change.
3. **Preview** inside the app: type any text. With "Type through my keyboard keys" ticked, plain letters are turned into your private-use letters.

## 4. Use it on Android

- Draw, then **Export font** to send the `.ttf` to your PC (WhatsApp, Drive, USB, …) or to friends.
- **Type & share** opens a screen with your letters as keys. Type there (your phone keyboard's QWERTY keys also turn into your letters) and **Share as picture**.
- Android doesn't allow normal apps to install system-wide fonts, so the font shows inside DrawFont only. Other apps need pictures (below) or a PC.

### Move your alphabet between phone and PC (no redrawing)

1. **Phone:** draw, then **Export font** and send the `.ttf` to yourself (WhatsApp "Saved messages"/chat with yourself, Google Drive, email, USB cable…).
2. **PC, use it:** double-click the `.ttf` → **Install** (section 3).
3. **PC, keep editing:** in DrawFont choose **File → Open project or font…** and pick the same `.ttf`. Your drawings appear exactly as on the phone.
   Redraw a letter, export a new font, make pictures, or **Export Windows keyboard layout (.klc)** — all from that one file.
4. **Other direction:** on the phone tap **Import font / project** and pick a `.ttf` (or project `.json`) made on the PC.

The hidden drawing data is ignored by Word, browsers and the operating system, so the font behaves like any other font. Anyone you give the `.ttf`
to can open it in DrawFont and edit your drawings — share it like you would share the source of your handwriting.
Fonts exported by older versions of DrawFont don't have the data; export once more from the project file.

## 5. Sharing with friends (WhatsApp, Discord)

WhatsApp, Discord and most chat apps draw text in **their own font**, so a friend cannot see your font inside a chat. What works:

- **A picture of your text:** Windows **File → Export preview text as picture (.png)** (transparent background if you like) or Android **Share as picture**. Everyone sees your handwriting.
- **The font file** (`.ttf`) for friends to install on their PC, and the Releases link so they can make their own alphabet.
- **The same `.ttf`** is also all they need to edit your drawings in DrawFont (**File → Open project or font…**). A project `.json` works too.

## 6. Publish it on GitHub (one time)

1. Create a repository on github.com (Public).
2. Upload everything in this folder. **The hidden `.github` folder often does not upload by drag-and-drop**: after uploading, check that
   `.github/workflows/build.yml` exists. If not, use **Add file → Create new file**, type `.github/workflows/build.yml` as the name
   and paste in the file's contents.
3. Open `version.py` and change `REPO = "..."` to your `username/repository` if it differs.
4. **Releases → Draft a new release →** new tag `v1.0.0` → **Publish release**.
5. Open the **Actions** tab. When **Build apps** is green (about 10–15 minutes), the three files appear under the release.

### Updating later

Change the code (or just re-upload it), then publish a release with a **higher tag** (`v1.0.1`, `v1.1.0` …). The workflow writes the tag
into the apps as their version number.

**Auto-update:** DrawFont checks your latest release at startup (Help → Check for updates also works).
Installed Windows copies download `DrawFont-Setup.exe`, verify it came from your releases and its size matched, ask you, install quietly and reopen.
Android shows an "Update available" dialog; tap **Download**, then open the new `.apk` (Android asks you to confirm — apps can't silently update themselves outside the Play Store).

### Android signing (read once)

Android only updates an app if the new version is signed with the **same key**. This repository includes one key
(`android/drawfont-sideload.p12.b64`, password `drawfont-sideload`) so that every release can update the last one. That key is public, which is fine for a
hobby app that people install by hand, but it means anyone could build an app that Android would treat as an update of yours.
If you want to publish seriously, make your own private key and keep it in GitHub **Secrets**.

## 7. Run from source (Python 3.8+)

```
pip install -r requirements.txt
python drawfont.py
```
On Linux you also need `sudo apt install python3-tk`. Tests (no screen needed): `python -m unittest discover -s . -p "test_*.py"`.

## How it works

- `fontcore.py` — the engine, no GUI: strokes → outlines of a round pen → TrueType font (+ PNG export). Shared by Windows **and** Android (the Android app runs this same file through [Chaquopy](https://chaquo.com/chaquopy/)).
- `kblayout.py` — writes the `.klc` keyboard layout. `updater.py` — update checks. `drawfont.py` — Windows window (Tkinter).
- `android/` — the Android app (Kotlin). `installer/drawfont.iss` — Windows installer script (Inno Setup).

## Known limits

- Fonts are made of pen strokes (like a marker), not hand-drawn filled outlines. One style, no kerning or ligatures.
- The Windows keyboard layout needs Microsoft's MSKLC to build the installer (a Microsoft tool; DrawFont only writes its source file).
- The Android app was written without access to an Android device or SDK in the environment where it was created, so the first build may need fixes: if **Build apps → android** shows a red cross, open it and read the error.

MIT licence — free for personal and commercial use. Fonts you make are yours.
