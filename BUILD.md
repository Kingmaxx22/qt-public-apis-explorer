# Building a Windows executable

Requires [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
```

## One command

```bash
cd /d/Gawe/FreeApi
python tools/make_icon.py                      # assets/app.ico (skippable)
python -m PyInstaller QtPublicApis.spec --noconfirm
```

Result: `dist/QtPublicAPIs/QtPublicAPIs.exe` — a windowed app, no console.

## onedir vs onefile

The spec defaults to **onedir**, which is the right choice for a Qt app:

| | onedir (default) | onefile |
| --- | --- | --- |
| Startup | Fast | Unpacks ~120 MB to `%TEMP%` on **every** launch |
| Folder | `dist/QtPublicAPIs/` (~122 MB) | Single `.exe` (~60 MB) |
| Updates | Replace the folder | Replace one file |

For a single portable file, add the flag — the spec handles it:

```bash
python -m PyInstaller QtPublicApis.spec --noconfirm --onefile
```

## What is bundled

- `data/catalog.json` → the offline registry snapshot (2,020 APIs)
- `assets/fonts/*.ttf` → Inter + JetBrains Mono, with their OFL licenses
- `assets/app.ico` → multi-resolution app/taskbar icon

`qtapis/paths.py` resolves all of these through `sys._MEIPASS`, so the same
code works from source and from a frozen bundle.

## Where the catalog cache is written

A frozen onefile bundle extracts to a **read-only** temp directory, so a sync
or a favorite would silently fail to persist. `store.py` therefore reads from
the bundled snapshot but writes to:

```
dist/QtPublicAPIs/data/catalog.json      (next to the .exe)
```

Your favorites and the last sync survive restarts. Delete that file to reset to
the shipped snapshot.

## Verifying a build

A windowed build has no stdout, so "the process is alive" proves nothing — a
failure dialog would also stay alive. Use the built-in self-test instead, which
writes a JSON report and sets the exit code:

```bash
cd dist/QtPublicAPIs
./QtPublicAPIs.exe --selftest report.json
echo $?     # 0 = healthy, 1 = failed
cat report.json
```

It loads the catalog, resolves the fonts, and records the first parsed record:

```json
{
 "ok": true,
 "records": 2020,
 "categories": 51,
 "bundled_snapshot": "...\\_internal\\data\\catalog.json",
 "snapshot_exists": true,
 "fonts": { "Inter": "Inter", "JetBrains Mono": "JetBrains Mono" },
 "sans_family": "Inter",
 "mono_family": "JetBrains Mono",
 "first_record": { "name": "Axolotl", "auth": "none", "https": "yes", "cors": "no" }
}
```

`--selftest` works from source too:

```bash
python main.py --selftest report.json
```

## Size trimming

`QtPublicApis.spec` excludes ~40 unused Qt modules (WebEngine, Quick/QML, 3D,
Charts, Multimedia, Sql, …), which roughly halves the bundle. If you import a
Qt module the app does not currently use, add it to `EXCLUDED_QT`'s absence —
that is, remove it from the list — or the frozen build will fail at runtime.

## Notes

- **No console.** `console=False` means no terminal window, which also keeps the
  app well-behaved under a tiling window manager. Use `--selftest` for logs.
- **No code signing.** Windows SmartScreen will warn on first run. Add a
  `version_info.txt` and sign the binary for distribution.
- **Antivirus false positives** are common with unsigned PyInstaller binaries
  that embed Qt; sign the artifact rather than disabling protection.
