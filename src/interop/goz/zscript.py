"""Mirai's ZBrush import script for an object with morph targets (AD-029 §3, option a; T11/T11b). Stdlib only.

Why (Manu, reference PC, 2026-11-06): ZBrush always puts several objects of one `GoZ_ObjectList.txt` into one Tool as
SubTools (T11b, also with *Import as SubTool* off), and its own GoZ import cannot update them: every `.ztn` it writes
names the Tool, and each file goes into the SubTool of the Tool's name (T11: six SubTools, the base renamed). GoB, the
Blender bridge, met the same in 2020 and replaced ZBrush's import with its own ZScript (read for behaviour only, no
code taken; `JoseConseco/GoB` `ZScripts/GoB_Import.txt`).

How:

- The script is **fixed** (no per-send code): `GoZApps\\Mirai\\MiraiGoZ_Import.txt`, rendered with the absolute paths of
  its list and result file. ZBrush runs compiled `.zsc` scripts; the artist loads the `.txt` once (*ZScript > Load*),
  ZBrush compiles it to `MiraiGoZ_Import.zsc` beside it. Mirai sends only while that `.zsc` is newer than the `.txt`;
  a changed script (new version) asks for one more load.
- Per send Mirai writes `MiraiGoZ_List.txt` (CRLF): a token, the GoZ project folder (forward slashes, trailing `/`),
  then the file names (base first, then each target). Then `ZBrush.exe <…\\MiraiGoZ_Import.zsc>` (path from
  `GoZBrush\\GoZ_Config.txt`); a running ZBrush takes the script (Manu 2026-11-06).
- The script: for each name, the SubTool of exactly that name in the **active** Tool (lowest subdivision level,
  `Tool:Import` of the `.GoZ`; ZBrush names a SubTool after the imported file, so the next send finds it again). The
  base not in the active Tool → a new Tool from the base; a target not there → a new SubTool. It writes
  `MiraiGoZ_Result.txt`: the token, then `updated:` / `added:` / `tool:` / `missing:` per name; a list whose token is
  already in the result is not imported again (loading the `.txt` runs the script once).
- Mirai writes only into its own app folder; no `.ztn`, no `.ztl`, no ZBrush setting (AD-029 §3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from .files import GozPaths, GozSetupError, read_text, write_text_atomic

SCRIPT_VERSION = 1
SCRIPT_STEM = "MiraiGoZ_Import"
LIST_FILE = "MiraiGoZ_List.txt"
RESULT_FILE = "MiraiGoZ_Result.txt"

#: The ZScript, `{list}` / `{result}` / `{version}` filled in. ZScript notes, as used by GoB's working import on
#: ZBrush 2021+: `StrFind(needle, haystack)` is 0-based, -1 = not found; `IGetTitle "Tool:ItemInfo"` is the active
#: SubTool's name plus one trailing character; `MemReadString(..., 1)` stops at the line end, returns the bytes read
#: including it; `Tool:SubTool:Insert` + `PopUp:PolyMesh3D` inserts a SubTool and selects it.
TEMPLATE = r"""// Mirai GoZ import, version {version} (AD-029 §3). Written by Mirai's "ZBrush: Mirai bei GoZ eintragen".
// Load once: ZScript > Load > this file. ZBrush compiles it to MiraiGoZ_Import.zsc beside it, and Mirai
// starts ZBrush.exe with that .zsc whenever it sends an object with morph targets.

[VarDef,mgList,"{list}"]
[VarDef,mgResult,"{result}"]
[VarDef,mgToken,""]
[VarDef,mgDone,""]
[VarDef,mgFolder,""]
[VarDef,mgLine,""]
[VarDef,mgName,""]
[VarDef,mgPath,""]
[VarDef,mgSub,""]
[VarDef,mgReport,""]
[VarDef,mgPos,0]
[VarDef,mgBytes,0]
[VarDef,mgIndex,0]
[VarDef,mgTotal,0]
[VarDef,mgFound,-1]
[VarDef,mgCount,0]
[VarDef,mgSkip,1]

// the active SubTool's name (ItemInfo carries one more character)
[RoutineDef,MgActiveName,
    [VarSet,mgSub,[IGetTitle,"Tool:ItemInfo"]]
    [VarSet,mgSub,[StrExtract,mgSub,0,[StrLength,mgSub]-2]]
]

// mgFound = index of the SubTool named mgName in the active Tool, -1 if there is none
[RoutineDef,MgFind,
    [VarSet,mgFound,-1]
    [VarSet,mgIndex,0]
    [VarSet,mgTotal,[SubToolGetCount]]
    [Loop,mgTotal,
        [SubToolSelect,mgIndex]
        [RoutineCall,MgActiveName]
        [If,([StrLength,mgSub]==[StrLength,mgName]) && ([StrFind,mgSub,mgName]==0),
            [VarSet,mgFound,mgIndex]
            [LoopExit]
        ]
        [VarInc,mgIndex]
    ]
]

// the lowest subdivision level before an import, so ZBrush keeps the higher ones
[RoutineDef,MgBaseLevel,
    [If,[IExists,Tool:Geometry:SDiv],
        [If,[IsEnabled,Tool:Geometry:SDiv],
            [ISet,Tool:Geometry:SDiv,1]
        ]
    ]
]

// a new Tool from the file mgPath
[RoutineDef,MgNewTool,
    [IKeyPress,13,[IPress,Tool:Plane3D]]
    [FileNameSetNext,mgPath]
    [IPress,Tool:Import]
    [CanvasClick,10,10,10,20]
    [IPress,Transform: Edit]
]

// a new SubTool of the active Tool from the file mgPath
[RoutineDef,MgNewSubTool,
    [RoutineCall,MgActiveName]
    [IPress,Tool:SubTool:Insert]
    [If,[StrFind,"PolyMesh3D",mgSub]>-1,
        [IPress,PopUp:Cube3D]
    ,
        [IPress,PopUp:PolyMesh3D]
    ]
    [FileNameSetNext,mgPath]
    [IPress,Tool:Import]
]

// mgLine = the next line of the list (empty at its end)
[RoutineDef,MgReadLine,
    [VarSet,mgLine,""]
    [If,mgPos < [MemGetSize,MgListMem],
        [VarSet,mgBytes,[MemReadString,MgListMem,mgLine,mgPos,1]]
        [VarSet,mgPos,mgPos+mgBytes]
    ]
]

[If,[FileExists,mgList],
    [If,[MemGetSize,MgListMem],[MemDelete,MgListMem]]
    [MemCreateFromFile,MgListMem,mgList]
    [VarSet,mgPos,0]
    [RoutineCall,MgReadLine]
    [VarSet,mgToken,mgLine]
    [If,[FileExists,mgResult],
        [If,[MemGetSize,MgResultMem],[MemDelete,MgResultMem]]
        [MemCreateFromFile,MgResultMem,mgResult]
        [MemReadString,MgResultMem,mgDone,0,1]
        [MemDelete,MgResultMem]
    ]
    [VarSet,mgSkip,1]
    [If,[StrLength,mgToken]>0,[VarSet,mgSkip,0]]
    [If,([StrLength,mgDone]==[StrLength,mgToken]) && ([StrFind,mgDone,mgToken]==0),[VarSet,mgSkip,1]]
    [If,mgSkip==0,
        [RoutineCall,MgReadLine]
        [VarSet,mgFolder,mgLine]
        [VarSet,mgReport,[StrMerge,mgToken,[StrFromAsc,10]]]
        [VarSet,mgCount,0]
        [Loop,999,
            [RoutineCall,MgReadLine]
            [If,[StrLength,mgLine]==0,[LoopExit]]
            [VarSet,mgName,mgLine]
            [VarSet,mgPath,[StrMerge,mgFolder,mgName,".GoZ"]]
            [If,[FileExists,mgPath],
                [RoutineCall,MgFind]
                [If,mgFound>-1,
                    [SubToolSelect,mgFound]
                    [RoutineCall,MgBaseLevel]
                    [FileNameSetNext,mgPath]
                    [IPress,Tool:Import]
                    [VarSet,mgReport,[StrMerge,mgReport,"updated:",mgName,[StrFromAsc,10]]]
                ,
                    [If,mgCount==0,
                        [RoutineCall,MgNewTool]
                        [VarSet,mgReport,[StrMerge,mgReport,"tool:",mgName,[StrFromAsc,10]]]
                    ,
                        [RoutineCall,MgNewSubTool]
                        [VarSet,mgReport,[StrMerge,mgReport,"added:",mgName,[StrFromAsc,10]]]
                    ]
                ]
            ,
                [VarSet,mgReport,[StrMerge,mgReport,"missing:",mgName,[StrFromAsc,10]]]
            ]
            [VarInc,mgCount]
        ]
        [MemDelete,MgListMem]
        [IPress,Transform: Fit]
        [If,[MemGetSize,MgResultOut],[MemDelete,MgResultOut]]
        [MemCreate,MgResultOut,[StrLength,mgReport],0]
        [MemWriteString,MgResultOut,mgReport,0,0]
        [MemSaveToFile,MgResultOut,mgResult,1]
        [MemDelete,MgResultOut]
    ,
        [MemDelete,MgListMem]
    ]
]
"""


def _fwd(path: Path) -> str:
    return str(path).replace("\\", "/")


def script_paths(paths: GozPaths) -> tuple[Path, Path]:
    return paths.app_dir / f"{SCRIPT_STEM}.txt", paths.app_dir / f"{SCRIPT_STEM}.zsc"


def render_script(paths: GozPaths) -> str:
    return (TEMPLATE.replace("{list}", _fwd(paths.app_dir / LIST_FILE))
            .replace("{result}", _fwd(paths.app_dir / RESULT_FILE))
            .replace("{version}", str(SCRIPT_VERSION)))


def write_script(paths: GozPaths) -> Path:
    """The `.txt` in Mirai's app folder, rewritten only when its content changed (so a loaded `.zsc` stays valid)."""
    txt, _zsc = script_paths(paths)
    text = render_script(paths).replace("\n", "\r\n")
    if read_text(txt) != text:
        write_text_atomic(txt, text, encoding="utf-8", newline="")
    return txt


def require_compiled(paths: GozPaths) -> Path:
    """The compiled script ZBrush made from the current `.txt`; else `GozSetupError` saying what to load. Nothing of a
    send is written before this passes."""
    txt = write_script(paths)
    _txt, zsc = script_paths(paths)
    if not zsc.is_file():
        raise GozSetupError(f"nothing sent - an object with morph targets needs Mirai's import script once: in ZBrush "
                            f"ZScript > Load > {txt} (ZBrush's own GoZ puts several SubTools in the wrong place, T11)")
    if zsc.stat().st_mtime < txt.stat().st_mtime:
        raise GozSetupError(f"nothing sent - Mirai's import script changed: in ZBrush ZScript > Load > {txt} once more")
    return zsc


def write_list(paths: GozPaths, token: str, project: Path, stems: Sequence[str]) -> Path:
    target = paths.app_dir / LIST_FILE
    folder = _fwd(project).rstrip("/") + "/"
    write_text_atomic(target, "\r\n".join([token, folder, *stems]) + "\r\n", encoding="utf-8", newline="")
    return target


@dataclass
class ImportResult:
    token: str
    entries: list[tuple[str, str]] = field(default_factory=list)  # (updated / added / tool / missing, name)

    def summary(self) -> str:
        counts: dict[str, int] = {}
        for what, _name in self.entries:
            counts[what] = counts.get(what, 0) + 1
        words = {"updated": "updated", "added": "added as SubTool", "tool": "as a new Tool", "missing": "file missing"}
        return ", ".join(f"{n} {words.get(w, w)}" for w, n in counts.items()) or "nothing imported"


def read_result(paths: GozPaths) -> Optional[ImportResult]:
    text = read_text(paths.app_dir / RESULT_FILE)
    if not text:
        return None
    lines = [line.strip("\0\r ") for line in text.split("\n")]
    out = ImportResult(lines[0])
    for line in lines[1:]:
        what, _sep, name = line.partition(":")
        if name:
            out.entries.append((what, name))
    return out


def _zbrush_exe_from_config(config_path: Path) -> Optional[Path]:
    """`PATH = "..."` of `GoZBrush\\GoZ_Config.txt` (ZBrush writes it)."""
    text = read_text(config_path)
    m = re.search(r'PATH\s*=\s*"([^"]+)"', text or "")
    return Path(m.group(1)) if m else None


def zbrush_exe(paths: GozPaths) -> Path:
    exe = _zbrush_exe_from_config(paths.gozbrush / "GoZ_Config.txt")
    if exe is None:
        raise GozSetupError("ZBrush.exe not named in GoZBrush\\GoZ_Config.txt: start ZBrush once so it writes the file")
    if not exe.is_file():
        raise GozSetupError(f"{exe} not found (GoZBrush\\GoZ_Config.txt): start ZBrush once so it writes the file")
    return exe
