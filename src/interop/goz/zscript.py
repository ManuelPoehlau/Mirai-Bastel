"""ZScript generation for Mirai's multi-SubTool GoZ send (option a, AD-029 §3).

GoZ sends multiple objects in one GoZ_ObjectList; ZBrush always groups them into one Tool with SubTools,
regardless of Import-as-SubTool (T11b confirmed 2026-11-06, B).  This module:
- writes one .ztn per object (each pointing to its own identifier so GoZ returns reach the right file)
- generates a ZScript that finds each SubTool by exact name in the active Tool and imports the GoZ into it,
  or appends a new SubTool when the name is not found (first-send case)
- launches ZBrush.exe directly with the script path (single-instance: script runs in running ZBrush;
  confirmed Manu 2026-11-06)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Sequence


def ztn_content(identifier: str) -> str:
    """The identifier without extension, no newline — the 55-byte format confirmed in T11 captures.

    ZBrush reads this file to find which SubTool a GoZ return belongs to.  By writing the correct
    per-object identifier here (instead of the Tool name ZBrush would write), we tell ZBrush
    exactly where each file belongs.  Tool:Import in ZScript does NOT overwrite these."""
    return identifier


def write_ztn_files(project: Path, identifiers: Sequence[str]) -> None:
    """Write one <stem>.ztn per identifier into the project folder, ANSI encoding, no newline.

    Must be called BEFORE launching ZBrush so the files are in place when ZBrush processes the
    GoZ_ObjectList.  Tool:Import via ZScript does not write .ztn files, so our pre-written ones
    survive (confirmed AD-029 §3)."""
    from .files import ansi_encoding, write_text_atomic

    for identifier in identifiers:
        stem = Path(identifier).stem
        ztn_path = project / (stem + ".ztn")
        write_text_atomic(ztn_path, ztn_content(identifier), encoding=ansi_encoding(), newline="")


def _zbrush_exe_from_config(config_path: Path) -> Optional[Path]:
    """Parse PATH = "..." from GoZ_Config.txt (the file ZBrush writes on the R > <app> pick)."""
    try:
        text = config_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        try:
            text = config_path.read_bytes().decode("latin-1")
        except OSError:
            return None
    # GoZ_Config.txt format: PATH = "C:/path/to/ZBrush.exe"\r\n
    m = re.search(r'PATH\s*=\s*"([^"]+)"', text)
    if not m:
        return None
    return Path(m.group(1))


def zbrush_exe(paths) -> Path:
    """Path to ZBrush.exe from the GoZ_Config.txt written by ZBrush.

    Raises GozSetupError if the file is missing or the path is not found."""
    from .files import GozSetupError

    result = _zbrush_exe_from_config(paths.gozbrush / "GoZ_Config.txt")
    if result is None:
        raise GozSetupError(
            "ZBrush.exe path not found in GoZ_Config.txt: start ZBrush once so it writes the file"
        )
    return result


def make_import_script(objects: Sequence[tuple[str, str]]) -> str:
    """Generate a ZScript that imports each GoZ file into the matching SubTool of the active Tool.

    Each tuple is (stem, goz_path_str).  The script:
    - iterates over all SubTools by index using [ISet,"Tool:SubTool:Sub T",n]
    - reads the name with [IGetTitle,"Tool"] — hypothesis: returns the active SubTool's mesh name
      (may need adjustment if a different interface path is needed; documented as a hypothesis)
    - on exact name match: set SDiv to 1, then Tool:Import with the GoZ file path
    - if no SubTool matches by name: append a new SubTool with Tool:SubTool:Append
    - forward slashes in paths (ZBrush accepts both on Windows)

    ZScript API notes (hypotheses marked with [H]):
    - [IGetTitle,"Tool"] returns the active SubTool mesh name [H: may be active Tool name instead]
    - [StrFind] returns 1-based position, 0 if not found — exact-match check: found == 1 AND
      StrLength(result) == StrLength(stem) so a name that is a prefix does not match
    - [IGet,"Tool:SubTool:Sub T"] after [ISet] returns a value less than n when n is past the last
      SubTool, allowing a loop-exit check
    - [ISet,"Tool:Geometry:SDiv",1] selects base subdivision level before import
    """
    # Header: declare shared variables once
    lines = ["[VarDef,_mi_found,0][VarDef,_mi_i,0]"]

    for stem, goz_path in objects:
        # Use forward slashes; ZBrush accepts both on Windows
        fwd_path = goz_path.replace("\\", "/")

        block = _make_object_block(stem, fwd_path)
        lines.append(block)

    return "\n".join(lines) + "\n"


def _make_object_block(stem: str, goz_path: str) -> str:
    """One ZScript block: find the SubTool named `stem` in the active Tool and import `goz_path`.

    If not found, append a new SubTool.  Uses nested [If] instead of && for safety (ZScript
    does not have a boolean AND operator; nested If is the idiomatic form)."""
    # We search up to 256 SubTools; in practice a Tool has far fewer.
    # [IGet,"Tool:SubTool:Sub T"] returns the actual selected index; if setting to n gives back
    # less than n, we have passed the last SubTool.
    max_subtools = 256

    # Build the per-SubTool name-check and import sequence.
    # ZScript is interpreted text; indentation is optional but we keep it flat for size.
    #
    # [H] [IGetTitle,"Tool"] returns the active SubTool's mesh name.
    # Exact-match: StrFind(title, stem) == 1  AND  StrLength(title) == StrLength(stem)
    # (StrFind is 1-based; a pure prefix would match position 1 but have a shorter length.)

    stem_len = len(stem)

    block = (
        # Reset found flag for this object
        f"[VarSet,_mi_found,0]"
        # Loop over SubTool indices
        f"[VarSet,_mi_i,0]"
        f"[Loop,{max_subtools},"
        # Select SubTool at index _mi_i
        f"[ISet,\"Tool:SubTool:Sub T\",[VarGet,_mi_i]]"
        # Exit loop if we went past the last SubTool (IGet returns less than we set)
        f"[If,([IGet,\"Tool:SubTool:Sub T\"]<[VarGet,_mi_i]),[LoopExit]]"
        # Get the active SubTool's name
        f"[VarDef,_mi_title,[IGetTitle,\"Tool\"]]"
        # Check exact match: position 1 and same length
        f"[If,([StrFind,_mi_title,\"{stem}\"]==1),"
        f"[If,([StrLength,_mi_title]=={stem_len}),"
        # Match found: set SDiv to base level, import, mark found, exit loop
        f"[ISet,\"Tool:Geometry:SDiv\",1]"
        f"[FileNameSetNext,\"{goz_path}\"]"
        f"[IPress,\"Tool:Import\"]"
        f"[VarSet,_mi_found,1]"
        f"[LoopExit]"
        f"]"  # end inner If (length)
        f"]"  # end outer If (StrFind)
        # Advance index
        f"[VarSet,_mi_i,([VarGet,_mi_i]+1)]"
        f"]"  # end Loop
        # If not found (first send or SubTool was removed): append as new SubTool
        f"[If,([VarGet,_mi_found]==0),"
        f"[FileNameSetNext,\"{goz_path}\"]"
        f"[IPress,\"Tool:SubTool:Append\"]"
        f"]"
    )
    return block
