"""
updater.py - checks your GitHub Releases for a newer DrawFont and (on Windows) installs it.

Safety rules:
  * only talks to api.github.com and only downloads files from
    https://github.com/<REPO>/releases/download/...  (anything else is refused)
  * checks the downloaded size matches what GitHub reports before running it
  * never installs anything without the user pressing Yes
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

INSTALLER_NAME = "DrawFont-Setup.exe"
ANDROID_NAME = "DrawFont-Android.apk"
HEADERS = {"User-Agent": "DrawFont-updater", "Accept": "application/vnd.github+json"}


class UpdateError(Exception):
    pass


def parse_version(text):
    """'v1.2.3-beta' -> (1, 2, 3). Unparseable -> ()."""
    return tuple(int(n) for n in re.findall(r"\d+", str(text).split("-")[0]))


def is_newer(latest, current):
    a, b = parse_version(latest), parse_version(current)
    if not a or not b:
        return False
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def fetch_latest(repo, opener=urllib.request.urlopen, timeout=8):
    """Latest release as {version, notes, page, assets:[{name,url,size}]}; None if there are no releases yet."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        with opener(urllib.request.Request(url, headers=HEADERS), timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        if ex.code == 404:
            return None
        raise UpdateError(f"GitHub answered with error {ex.code}.") from ex
    except (OSError, ValueError) as ex:
        raise UpdateError("Could not reach GitHub. Check your internet connection.") from ex
    return {
        "version": str(data.get("tag_name") or "").lstrip("vV"),
        "notes": str(data.get("body") or ""),
        "page": str(data.get("html_url") or f"https://github.com/{repo}/releases"),
        "assets": [{"name": a.get("name", ""), "url": a.get("browser_download_url", ""), "size": a.get("size")}
                   for a in data.get("assets") or []],
    }


def pick_asset(release, name):
    return next((a for a in release["assets"] if a["name"] == name), None)


def download(url, dest, repo, expected_size=None, opener=urllib.request.urlopen, progress=None):
    if not url.startswith(f"https://github.com/{repo}/releases/download/"):
        raise UpdateError("Refusing to download from an unexpected address.")
    tmp = dest + ".part"
    total = 0
    try:
        with opener(urllib.request.Request(url, headers=HEADERS), timeout=30) as r, open(tmp, "wb") as f:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
                if progress:
                    progress(total)
        if expected_size and total != expected_size:
            raise UpdateError("The download was incomplete. Please try again.")
        os.replace(tmp, dest)
    except UpdateError:
        _silent_remove(tmp)
        raise
    except OSError as ex:
        _silent_remove(tmp)
        raise UpdateError(f"Download failed: {ex}") from ex


def _silent_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def run_installer(path, popen=subprocess.Popen):
    """Start the installer detached and quietly (Windows). The caller should exit right after."""
    flags = 0x00000008 | 0x00000200 if sys.platform == "win32" else 0     # DETACHED | NEW_GROUP
    popen([path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], close_fds=True, creationflags=flags)
