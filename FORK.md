# Orca Enhanced (OrcaSlicer-Enhanced) — fork notes

What differs in this fork from OrcaSlicer, and how to maintain it. Upstream's own guidance is in `AGENTS.md`.

**The canonical checkout is `C:\Program Files\Purple-OrcaSlicer`.** The folder keeps its old name: both build
trees hold absolute paths to it. It is a full source tree built in place, not an install directory: the desktop
shortcut `Orca.lnk` and the Start-menu `OrcaSlicer\Orca.lnk` both run `build\src\Release\orca-slicer.exe`
(start-in folder `build\src\Release`), so every build is live at the next start (verified 2026-10-18). The app
code is `OrcaSlicer.dll`; `orca-slicer.exe` is a thin launcher that only relinks when its own sources change,
so judge a build by the DLL's timestamp. Version `2.5.0-Kurisu`
(`version.inc`, `SoftFever_VERSION`): upstream bumps the number, the fork keeps the `-Kurisu` suffix. The app's
internal key stays `OrcaSlicer` (`SLIC3R_APP_KEY`), so it shares `%APPDATA%\OrcaSlicer` (presets, printers) with
stock Orca; renaming it would strand the owner's presets.

## What the fork is

OrcaSlicer `main` plus, as separate commits on top of it:

1. **Purple accent theme (#B13CFF)** — the output of `scripts/purple_theme.py`, then the hand edits the
   palette can't express (purple app icons/logos, side-button and tab hover shades, a few blue and Bambu-green
   accents, gizmo highlights).
2. **Branding** — `-Kurisu` version, About-dialog link to this repo, renamed-fork Flatpak artifact path, and the
   update check reading this repo's releases.
3. **Features ported from NanashiTheNameless/OrcaSlicer** — wave overhangs, staggered perimeters, odd-even wall
   order (see *Fork features*).
4. **Continuous walls across modifiers** — classic and Arachne (see *Fork features*).

### History

Until 2026-10-16 the fork was `Purple-OrcaSlicer`, a branch of Nanashi's fork of OrcaSlicer, updated by merging
`nanashi/main`. On 2026-10-17 it was rebuilt directly on OrcaSlicer `main` (`82aee1abdd`) as the commits above
and published as a fresh fork of OrcaSlicer/OrcaSlicer, `TheCorruptedEngineer/OrcaSlicer-Enhanced`, after merging
OrcaSlicer main up to `1ee0b730a1`. The old
line, with its V2.4.0-Kurisu and V2.5.0-Kurisu (draft) releases, is kept in the plain repo
`TheCorruptedEngineer/Purple-OrcaSlicer-backup`, and locally at `backup-pre-rebase-20261016` (`45eb89cb41`).

Remotes: `origin` = TheCorruptedEngineer/OrcaSlicer-Enhanced, `upstream` = OrcaSlicer/OrcaSlicer,
`purple-backup` = the backup repo, `nanashi` = NanashiTheNameless/OrcaSlicer (only to pick up fixes to the
ported features).

## Updating from upstream

```bash
git fetch upstream main
git switch -c update-YYYYMMDD && git merge upstream/main     # on a branch, never straight onto main
```

**Conflicts in themed lines:** take upstream's side, then re-run the palette. The theme is only colour literals,
so it never needs a hand-merge:

```bash
py -3 scripts/purple_theme.py            # re-theme whatever teal upstream added
py -3 scripts/purple_theme.py --check    # idempotence: must report 0 files
py -3 scripts/purple_theme.py --scan     # teal shades the palette doesn't cover yet -> map them or exempt them
```

Exceptions to "take upstream": `version.inc` (keeps `-Kurisu`), the hand edits in commit "Carry the fork's
hand-made theme edits and purple app icons", and the feature code below. When upstream *moves* a colour (a
hardcoded literal becomes a `StateColor` member), take the refactor and let the palette purple the new place.

**Nanashi feature fixes:** Nanashi keeps fixing the ported features. To pick a fix up, cherry-pick or port that
commit; don't merge `nanashi/main`, which would bring back their branding, CI and defaults.

## The purple theme

`scripts/purple_theme.py` is the source of truth: `HEX` and `RGB` map every accent teal (primary, hover,
pressed, dark-mode hover, 10%/25% tints) to its purple in hex, integer and float forms, and a PNG whose visible
pixels are all one palette colour (a flat accent icon) is recoloured with its alpha kept. Bytes in, bytes out,
so no mojibake. `--verify BASE THEMED` replays the palette on one tree and diffs against another; the rest is
hand edits.

- `src/slic3r/GUI/Widgets/StateColor.cpp` — `gDarkColors` is a light→dark `std::map` built from an init-list:
  a duplicate key silently drops the second value. The script guards this (`KEEP_HEX`, `check_dark_map`).
- `src/slic3r/GUI/BitmapCache.cpp` — the SVG icon recolour table (`replaces`).
- `src/slic3r/GUI/Widgets/WebViewHostDialog.cpp` — `--orca-accent`, the CSS variable every web dialog uses.

**Hover and focus states live in separate files.** Bitmap-driven widgets (`Widgets/CheckBox.cpp`) pick a whole
different SVG per state: purpling `check_on.svg` does nothing for `check_on_focused.svg`, which stayed teal for
months. The hover teals are lighter shades (`#4db6ac`, `#33aba1`, `#52c7b8`) — all in the palette now. When
hand-theming anything, check its `_hover` / `_focused` / `_disabled` / `_dark` siblings.

**Outside `src/` and `resources/images|web`**, the script themes only `EXTRA_FILES`: Orca's own build-plate
artwork, `resources/profiles/Custom/orcaslicer_bed_texture.svg` (logo and corner marks on every printer without a
vendor bed texture). It was missed once, leaving a teal plate (2026-10-18).

**Do not purple** (the script's `EXCLUDE` / `SCAN_IGNORE`): `PresetBundle.cpp` (`#26A69A` is the default
filament colour written into projects), `Plater.cpp`'s filament swatch palette, vendor bed textures in
`resources/profiles`, `resources/flush` colour data, G-code viewer / libslic3r colours, colour pickers, the
terminal's ANSI palette, semantic success/error colours.

**Verify a theme change shipped** (compiling is not proof):

```powershell
$t=[Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes('build\src\Release\OrcaSlicer.dll'))
'#B13CFF','#C060FF','#8E2FBF' | % { "$_ -> " + ([regex]::Matches($t,[regex]::Escape($_))).Count }
```

## Building (Windows, this machine)

Visual Studio 18 (2026). `build_win.bat` replaced `build_release_vs.bat` upstream; it needs the VS environment:

```bat
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
cd /d "C:\Program Files\Purple-OrcaSlicer"
call build_win.bat -d            &:: dependencies (deps\build, ~12 GB)
call build_win.bat -s --tests    &:: slicer + unit tests (build\, ~18 GB)
call build_win.bat -h            &:: everything else (-D dry run, --slicer-target, --no-configure, -j, ...)
```

- `NoDefaultCurrentDirectoryInExePath=1` is set here: call the script by full path or `.\`.
- With little free memory, `-j 3` caps the build at 3 compilers (it sets `CL_MPCount`; MSBuild builds one
  project at a time).
- **Close every Orca running from `build\src\Release` before building.** The configure step copies the
  dependency DLLs there (`Permission denied` on `TKXCAF.dll` = Orca is open), and the link fails with
  `LNK1104`. If the owner has unsaved work open, don't kill it: a loaded EXE/DLL can be renamed aside
  (`OrcaSlicer.dll` → `OrcaSlicer.dll.prev`) and the running window keeps the old image.
- The post-build step deletes and re-copies `build\src\Release\python`. With Orca running it deletes all but the
  files Orca holds, then fails (seen 2026-10-16). Restore with
  `cp -rn deps/build/OrcaSlicer_dep/usr/local/libpython/. build/src/Release/python/` and check with `diff -rq`.
- **`unresolved external symbol prusaslicer_png_*` from `wxmsw33u_core.lib`** = libpng was compiled against a
  stale header. libpng's include path puts the *installed* `deps\build\OrcaSlicer_dep\usr\local\include` before
  its own build dir, so an incremental deps build compiles libpng with the previous run's `pnglibconf.h`, then
  installs the new one, which wxWidgets uses (hit 2026-10-17: May header without the `prusaslicer_` prefix). A
  fresh tree never sees it. Fix: delete `deps\build\dep_PNG-prefix\src\dep_PNG-build\png_static.dir\Release`
  and the `dep_PNG-build`/`-install`/`-done` stamps in `dep_PNG-stamp\Release`, run `build_win.bat -d -t dep_PNG`,
  and check with `dumpbin /linkermember:1 libpng16_static.lib | findstr png_read_info` (must show the prefix).
- `C:` runs nearly full. The two build trees take ~30 GB; check free space before a deps rebuild.
- Never edit source while a build is running. Never regex-edit source from PowerShell (it has mojibaked
  `mm/s²`, `°C` and em-dashes here before); detect with `rg 'Â[°²³]|â€[""”“–—]|âŒ˜' src/`.

Tests: `ctest -C Release` from `build\` (2,317 tests pass as of 2026-10-18, on OrcaSlicer main `1ee0b730a1`). The fork's own test is in
`tests/fff_print/test_perimeters.cpp` (`fff_print_tests.exe "[Perimeters]"`).

**Slicing from the command line** (`orca-slicer.exe --slice 0 --outputdir OUT project.3mf`): since OrcaSlicer
#15595/#15642 the CLI re-applies the inherited system preset for every setting the project's
`different_settings_to_system` doesn't list. A test copy of a project with edited settings must list those keys
there too, or the edits are silently dropped. Creality's bundled `Creality K2 0.4 nozzle` preset also sets
`retraction_distances_when_cut` to 30, outside its 10–18 range, so the CLI refuses K2 0.4 projects unless the
project overrides it (and lists it). The GUI is not affected.

---

## Fork features (behaviour that differs from upstream)

### Ported from Nanashi's fork

Carried over in one commit from `nanashi/main` @ `9a40425cc2`, restricted to these features (Nanashi's other
changes — their branding, CI, defaults such as developer/stealth mode on — were left out):

- **Wave overhangs** (`wave_overhangs`, `wave_overhang_*`, `src/libslic3r/WaveOverhangs/`): curved fronts that
  ripple out from the supported edge so steep overhangs print without supports. From
  dennisklappe/OrcaSlicer-WaveOverhangs via Nanashi.
- **Staggered perimeters** (`staggered_perimeters`, `staggered_perimeter_flow_ratio`), by Vipul Rajan. Arachne
  wall generator only; with Classic walls it has no effect.
- **Odd-even wall order** (`wall_infill_order` "odd-even wall/infill", `loop_sequence`, `even_loops_flow_ratio`,
  `even_loops_speed`, `outermost_wall_control`), by pi-squared-studio.

None of the three has unit tests (Nanashi's fork has none either). All three slice the owner's
`air_adapter_rev2.3mf` from the CLI (2026-10-17).

### Continuous walls across modifiers — `continuous_modifier_walls` (2026-10-16)

**Problem (stock Orca, Bambu Studio and PrusaSlicer all do this):** a modifier that changes `wall_loops` makes
`Layer::is_perimeter_compatible()` refuse to share a perimeter run, so each region is walled as its own island.
The modifier's cut becomes a real outline: an outer wall on each side, back to back — a seam on the surface and
a double wall through the part.

**Fix:** object setting *Strength → Walls → Continuous walls across modifiers*, **default on**, both wall
generators.
- `Layer::make_perimeters()` lets regions that differ *only* in a non-zero `wall_loops` share one run.
- `PerimeterGenerator` derives wall-count zones from `compatible_regions` (`collect_wall_count_zones`).
  `IslandWallCountZones` holds one island's zones: it walls the island once with the largest loop count, and
  `area_keeping(depth)` is the part of the island whose zones keep the wall at that depth.
- `trim_walls_to_zones` trims each wall deeper than a zone's count out of that zone — closed loops and open
  walls, order and direction kept, cut ends pulled back half a line width. It runs *after* the wall-order passes.
- **Classic** also keeps only the gaps beside loops a zone still has, and fills each zone from its own innermost
  loop.
- **Arachne**: the generation block is the `generate_walls(loop_number)` lambda (walls, inner contour, top
  surface for one count, including upstream's only-one-wall-top logic). The island is walled with the largest
  count; each zone with fewer walls calls it again with its own count and fills from that run's inner contour,
  because Arachne reports only the area inside the innermost wall it was asked for.
- Not covered, stock behaviour: modifiers with **0 walls**, and modifiers that change **any other** wall setting.

**Revert:** untick the option (print profile or per object); the walls are then stock again.

**Proof:** `tests/fff_print/test_perimeters.cpp` — *"A wall count modifier keeps the walls continuous across its
boundary"* (classic and Arachne × 4 wall orders × 3/6 and 6/3 walls). End to end on the owner's
`air_adapter_rev2.3mf` (6 walls, a 9-wall modifier, arc fitting off), outer wall running along the cut, measured
as wall length within 0.35 mm of and within 12° of the modifier's vertical faces:

| | option on | option off (stock) |
|---|---|---|
| Classic | 7.8 mm | 8,594 mm |
| Arachne | 5.7 mm | 8,595 mm |

The remainder sits where the part's own surface meets the cut. Odd-even wall order and wave overhangs keep the
same figure (7.8 mm); staggered perimeters under Arachne keeps 5.7 mm.

**Gotchas:**
- Trimming runs after the wall-order passes: odd-even `static_cast`s every perimeter to `ExtrusionLoop`, and
  Arachne only orients closed walls in `traverse_extrusions()`.
- `clip_inner_perimeters_in_zone()` (wave overhangs) looks reusable but is not: it clips thin walls and puts a
  cut loop's pieces in one path in Clipper's order.
- Heuristics that read `config->wall_loops` see the merged region's config (the one with the highest infill
  density).
- `Print::validate()`'s spiral-vase check calls `is_perimeter_compatible()` without zones on purpose: vase
  mode keeps rejecting regions that differ in wall count.
- `intersection_pl_in_order()` keeps cut pieces in the wall's order by carrying the distance along the wall in
  Z through `clip_extrusion()` (Z > 0 subject, Z == 0 clip, interpolated at cuts). Since upstream's Clipper2
  migration that is `ClipperZUtils::ZPath`; the contract is unchanged.

---

## Status / open items (2026-10-18)

- Published: `TheCorruptedEngineer/OrcaSlicer-Enhanced` `main` = local branch `upstream-rebase`. Publish with
  `git push origin upstream-rebase:main`, a fast-forward (merge upstream first; never force-push `main`).
  Local `main` still points at the old line; once the owner has tried the new build:
  `git branch -f main upstream-rebase`, then work on `main`.
- The README is upstream's with a fork banner on top; it has no fork download links yet. Publishing a
  `2.5.0-Kurisu` release is the owner's call; the in-app update check reads this repo's releases.
- `C:\Users\AdministratorCorrupt\OrcaSlicer-Kurisu-old` (~0.5 GB) is a runnable copy of the pre-rebuild build
  (its shortcut is gone; run its `orca-slicer.exe`). Delete it once the new build has proven itself.
- Considered next: an accent colour selectable in Preferences (default = this purple). Plan: have
  `purple_theme.py` write accessor calls instead of literals so upstream merges stay conflict-free; icons via
  `BitmapCache`'s recolour table; web pages via CSS variables.
