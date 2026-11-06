# Handoff: GoZ — base + morph targets resent into ZBrush land in the wrong SubTools (2026-11-06)

For an agent working **on Manu's PC** (Windows, ZBrush 2022.0.8, GoZ root `C:\Users\Public\Pixologic`), branch
`claude/quirky-mayer-o1zhbj`. Background: [AD-029](architecture/AD-029-ZBRUSH-GOZ-BRIDGE.md) §3 („Names“, open item
T11), §5; probe: [`experiments/goz_probe/README.md`](../experiments/goz_probe/README.md) §6 T10/T11/T11b. Move this file
to `docs/archive/` when the problem is solved.

## Status

- **Solved (container-tested, PC-confirmed):** Mirai names its SubTools itself (`src/interop/goz/names.py`, registry
  `goz/manifests/names.json`): `<Object>`, `<Object>_<Target>`, stable over restarts, no `GoZMakeObjectPath`, MESH name
  `GoZMesh_<file name>`. Manu's PC shows clean names (`SubD_Cube`, `SubD_Cube_Target_1..3`).
- **Open:** a **resend** of base + targets into ZBrush. Mirai writes the right four files (checked: names, list order
  base first, every file carries the base edit, only the edited target its own sculpt), but ZBrush puts them in the
  wrong place.

## Facts from the PC (Manu, 2026-11-06, `experiments/goz_probe/captures/*_names/names_log.json`)

1. First send of `SubD_Cube` + 3 targets: one Tool with 4 SubTools, names right (*Import as SubTool* was **on**).
2. ZBrush writes, at the same second as the load, a `<name>.ztn` beside each `.GoZ`; **every** `.ztn` (the targets'
   too) contains `C:\Users\Public\Pixologic\GoZProjects\Default\SubD_Cube`. A GoZ export of a target SubTool writes its
   `.GoZ`/`.ztn` and `SubD_Cube.ztl` (the whole Tool, 271 KB).
3. Resend with `SubD_Cube.ztl` present: an **extra Tool** (old state) appears; in the old Tool the base gets renamed.
4. Resend with the `.ztl` moved away by hand: no extra Tool, but **six** SubTools: `Target_1` (was the base),
   `Target_1`, `Target_2`, `Target_3`, `Target_2`, `Target_3`. Reading: ZBrush goes `.ztn` → Tool `SubD_Cube` → SubTool
   *named* `SubD_Cube`: base right, target 1 into the base too (renamed after its file), targets 2/3 appended.
5. *Import as SubTool* switched **off** → still SubTools (the open question, T11b).

## Next step (T11b — tell A from B)

Hypothesis **A**: the old `.ztn`/`.ztl` still link everything to `SubD_Cube`, the setting only applies to unlinked
objects. Hypothesis **B**: a GoZ list with several objects always becomes one Tool with SubTools.

1. Close ZBrush; move every `SubD_Cube*` file (`.GoZ`, `.ztn`, `.ztl`) in `GoZProjects\Default` to a backup folder
   (Manu agrees to this for diagnosis; Mirai's code itself must not do it, see constraints).
2. Start ZBrush, *Import as SubTool* off; `python -I experiments/goz_probe/probe_names.py` — `GoZ_Config.txt` shows
   `FALSE`?
3. Send from Mirai (SPACE → „An ZBrush senden“); run `probe_names.py` again: each `.ztn` reads „own Tool“ (→ A) or
   „SubTool of Tool 'SubD_Cube'“ (→ B). Then: target edit in ZBrush, GoZ, apply in Mirai, base edit, resend — right?

## Options once A/B is known (Manu decides; AD-029 §3)

- **A:** document „Import as SubTool off + clean folder“; Mirai may *read* `GoZ_Config.txt` / the `.ztn` and refuse or
  warn on a resend that ZBrush would misplace.
- **(a) own Mirai ZScript import**, as GoB does (`JoseConseco/GoB`, `ZScripts/GoB_Import.txt`, read for behaviour
  only — no code copy): read `GoZ_ObjectList.txt`, find each SubTool in the active Tool by exact name, select it,
  `Tool:Geometry:SDiv` 1, `Tool:Import`; else insert a new SubTool. GoB starts ZBrush with the script instead of
  `GoZBrushFromApp`. Open: does ZBrush run a script passed on start / to a running instance, does it need a compiled
  `.zsc`, do GoZ returns from such SubTools still come back under their names.
- **(c) one object per transfer:** send, wait until ZBrush has written that object's `.ztn` (read only), send the next.

## Constraints (do not break)

- AD-029 §3: Mirai's code writes **no** ZBrush file or setting except its own `.GoZ` (plus the protocol files
  `GoZ_ObjectList.txt`, `GoZ_Application.txt`). No `.ztn`/`.ztl` deletion, no `GoZ_Config.txt` change in code without
  Manu's explicit decision (GoB does both; Mirai does not).
- A return must never be applied to the wrong object (manifest + fingerprint, AD-029 §5).
- Tests: `pytest tests/test_goz_bridge.py tests/test_goz_format.py -q` (headless) and
  `pytest experiments/goz_probe/tests -q`. Update AD-029 §3/§5 and the probe README in the same commit.
- Input bindings / `config/keymap.json`: untouched (no key for GoZ, AD-013).
