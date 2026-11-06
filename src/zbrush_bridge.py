"""Mirai <-> ZBrush over GoZ in the SPACE menu (AD-029, P1, `PROVISIONAL`; like `src/obj_files.py`: no pyglet).

Rows (no key: a key only after Manu's "Taste passt", AD-013 addendum):

    An ZBrush senden                     the object (mode 4: the one selected object, else the edit object; the base
                                         while a morph target's view is open) -> ZBrush, as `(x, -y, -z)` of its
                                         world position; a resend of the same object updates the same SubTool
                                         Refused (nothing written) until ZBrush knows Mirai: registered, ZBrush
                                         restarted, Mirai picked with R (`install.known_to_zbrush`) - naming an
                                         unknown GoZ app crashed ZBrush 2022.0.8 (Manu, 2026-11-05)
    ZBrush übernehmen: <name> · <id>     a waiting same-topology return: its moved points and changed polygroups
                                         (P2a) into the object, one Undo step (D1, Manu 2026-11-05: only after this
                                         confirm)
    ZBrush als neues Objekt: <name> · …  a return that cannot go in place (topology changed, Mirai edited since the
                                         send, unknown object): a new object beside the original
    ZBrush verwerfen: <name> · <id>      forget a waiting return
    ZBrush: Mirai bei GoZ eintragen      only while `GoZApps\\Mirai` is missing: registers Mirai (D12), once

A return arrives when the artist presses GoZ in ZBrush: `Edit.bat` -> `interop/goz/helper.py` -> a ticket in
`goz/inbox/`; `tick()` (main loop, 4 per second) claims it, plans it (`interop.goz.bridge.plan_return`) and posts the
plan in the status line. Nothing is applied before the confirm row, and the plan is computed again at the confirm, so
a scene edited in between gives the current verdict, not the old one. Waiting tickets of a Mirai that was not running
are picked up at the next start (D11).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from core.ids import ObjectId
from core.scene import SceneObject
from core.selection import SelectionMode
from interop.goz import install as goz_install
from interop.goz.bridge import (
    ReturnKind,
    ReturnPlan,
    SendRefused,
    SymmetryInfo,
    build_send,
    invalid_plan,
    plan_return,
    rebase_manifest,
    short_name,
)
from interop.goz.files import GozPaths, GozSetupError, find_root, same_identifier
from interop.goz.format import GozMesh
from interop.goz.manifest import Manifest
from interop.goz.transfer import (
    Inbox,
    default_runner,
    launch_zbrush,
    make_identifier,
    read_manifest_text,
    write_manifest,
    write_send,
)

_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INBOX = _ROOT / "goz" / "inbox"
DEFAULT_MANIFESTS = _ROOT / "goz" / "manifests"
#: P3b: textures of returns while the scene is not saved (Manu 2026-11-06: else beside the scene)
DEFAULT_TEXTURES = _ROOT / "goz" / "textures"

SEND_LABEL = "An ZBrush senden"
APPLY_PREFIX = "ZBrush übernehmen: "
NEW_OBJECT_PREFIX = "ZBrush als neues Objekt: "
DROP_PREFIX = "ZBrush verwerfen: "
INSTALL_LABEL = "ZBrush: Mirai bei GoZ eintragen"
POLL_SECONDS = 0.25


@dataclass
class Waiting:
    identifier: str
    goz: GozMesh
    manifest: Optional[Manifest]
    plan: ReturnPlan
    #: P3b: the copy of the texture this return named (made at arrival: ZBrush overwrites its file at the next GoZ)
    texture: Optional[str] = None

    @property
    def tag(self) -> str:
        return f"{self.plan.label} · {self.identifier.replace(chr(92), '/').rsplit('/', 1)[-1]}"


def symmetry_info(mesh) -> Optional[SymmetryInfo]:
    """The mesh's mirror pairs and seam points by Mirai's exact rule (`mirai.symmetry.vertex_correspondence`), or None
    while its symmetry is off (then a return comes exactly as ZBrush sends it; Manu 2026-11-05)."""
    from mirai.symmetry import CorrespondenceState, mirror_position, vertex_correspondence

    definition = mesh.symmetry_definition
    if definition is None:
        return None
    pairs, seam = [], []
    for vid, corr in vertex_correspondence(mesh).items():
        if corr.state is CorrespondenceState.SEAM:
            seam.append(vid)
        elif corr.state is CorrespondenceState.PAIRED and vid < corr.partner:
            pairs.append((vid, corr.partner))
    point, normal = definition.plane_point, definition.plane_normal
    return SymmetryInfo(tuple(pairs), tuple(seam), lambda p: mirror_position(p, point, normal))


def _triangulate():
    from viewport.derived import triangulate_face  # core-only ear clipping, the one Mirai renders and picks with

    return triangulate_face


def _placement():
    from mirai import object_space

    return object_space.to_world, object_space.to_object


class ZBrushBridge:
    def __init__(
        self,
        app,
        *,
        root: Optional[Path] = None,
        inbox: Path = DEFAULT_INBOX,
        manifests: Path = DEFAULT_MANIFESTS,
        textures: Path = DEFAULT_TEXTURES,
        scene_path: Callable[[], Optional[Path]] = lambda: None,
        runner=default_runner,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.app = app
        self._root = root
        self.inbox = Inbox(inbox)
        self.manifest_dir = Path(manifests)
        self.texture_dir = Path(textures)
        self._scene_path = scene_path
        self._runner = runner
        self._clock = clock
        self._last_poll = float("-inf")
        self.session_id = uuid.uuid4().hex
        #: per (object, None = base / LayerId = target) its GoZ identifier
        self._identifiers: dict[tuple, str] = {}
        #: per identifier the manifest versions of this session, oldest first: the send, then one per applied return,
        #: so a return after an Undo of an apply links to the version the object is back at (no resend needed)
        self._manifests: dict[str, list[Manifest]] = {}
        self.waiting: list[Waiting] = []
        self._rows: dict[str, tuple[str, Waiting]] = {}

    # -- menu ---------------------------------------------------------------------------------------------------------

    def paths(self) -> GozPaths:
        return GozPaths(find_root(self._root))

    def entries(self) -> tuple[str, ...]:
        self._rows = {}
        for w in self.waiting:
            if w.plan.in_place:
                self._rows[APPLY_PREFIX + w.tag] = ("apply", w)
            elif w.plan.new_object:
                self._rows[NEW_OBJECT_PREFIX + w.tag] = ("apply", w)
            self._rows[DROP_PREFIX + w.tag] = ("drop", w)
        rows = (SEND_LABEL,) + tuple(self._rows)
        try:
            paths = self.paths()
            if paths.gozbrush.is_dir() and not goz_install.is_installed(paths):
                rows += (INSTALL_LABEL,)
        except GozSetupError:
            pass
        return rows

    def handles(self, label: str) -> bool:
        return label in (SEND_LABEL, INSTALL_LABEL) or label in self._rows

    def activate(self, label: str) -> bool:
        if label == SEND_LABEL:
            return self.send()
        if label == INSTALL_LABEL:
            return self.install()
        action, w = self._rows.get(label, (None, None))
        if w is None:
            return False
        if action == "drop":
            self._forget(w)
            self.app.set_status(f"ZBrush {w.plan.label!r}: return dropped")
            return True
        try:
            return self.confirm(w)
        except Exception as exc:  # e.g. ZBrush topology the Mesh refuses for a new object; the scene is untouched
            self.app.set_status(f"ZBrush {w.plan.label!r}: failed: {type(exc).__name__}: {exc}")
            return False

    def refuse_add(self, label: str) -> bool:
        self.app.set_status(f"{label!r}: not as a Reference")
        return False

    # -- send ---------------------------------------------------------------------------------------------------------

    def pick_object(self) -> Optional[SceneObject]:
        app = self.app
        if app.selection.mode is not SelectionMode.OBJECT:
            return app.morph_document_object
        chosen = [app.scene.objects[oid] for oid in sorted(app.selection.objects) if oid in app.scene.objects]
        if len(chosen) != 1:
            app.set_status("ZBrush: select exactly one object (mode 4), or leave mode 4 for the edited one")
            return None
        if chosen[0] is app.scene.edit_object and app.morph_document_object is not chosen[0]:
            return app.morph_document_object
        return chosen[0]

    def send(self) -> bool:
        app = self.app
        owner = app.interaction_owner
        if owner is not None:
            app.set_status(f"ZBrush: not while the {owner} interaction runs")
            return False
        obj = self.pick_object()
        if obj is None:
            return False
        to_world, _ = _placement()
        try:
            paths = self.paths()
            if not paths.gozbrush.is_dir():
                raise GozSetupError(f"{paths.gozbrush} missing: is GoZ installed? (start ZBrush once)")
            if not goz_install.is_installed(paths):
                app.set_status(f"ZBrush: nothing sent - register Mirai first (SPACE > {INSTALL_LABEL!r}), restart "
                               "ZBrush, choose 'Mirai' with R beside the GoZ button, then send")
                return False
            if not goz_install.known_to_zbrush(paths):
                app.set_status("ZBrush: nothing sent - ZBrush does not know Mirai yet: restart ZBrush, choose 'Mirai' "
                               "with R beside the GoZ button once, then send")
                return False
            from mirai.morph_targets import morph_target_ids

            scene_path = self._scene_path()
            transfer_id = uuid.uuid4().hex
            sends = []  # (key, identifier, data, manifest): the base first, then each morph target (P3c)
            for layer in [None, *morph_target_ids(obj.mesh)]:
                key = (obj.id, None if layer is None else int(layer))
                title = obj.name if layer is None else f"{obj.name}_{obj.mesh.point_layer_info(layer).name}"
                identifier = self._identifiers.get(key) or make_identifier(paths, short_name(title),
                                                                           runner=self._runner)
                self._identifiers[key] = identifier
                data, manifest = build_send(
                    app.scene, obj, identifier=identifier, transfer_id=transfer_id, session_id=self.session_id,
                    scene_path=None if scene_path is None else str(Path(scene_path).resolve()), to_world=to_world,
                    triangulate=_triangulate(), symmetry=symmetry_info(obj.mesh), layer=layer,
                )
                sends.append((key, identifier, data, manifest))
            for _key_, identifier, _data, manifest in sends:
                write_manifest(self.manifest_dir, identifier, manifest.to_json())
            _k, identifier, data, manifest = sends[0]
            write_send(paths, identifier, data, [(i, d) for _k2, i, d, _m in sends[1:]])
            launch_zbrush(paths, runner=self._runner)
        except (SendRefused, GozSetupError, OSError) as exc:
            app.set_status(f"ZBrush: {exc}")
            return False
        except Exception as exc:  # a bug must show in the status line, never as a silent menu row (2026-11-05)
            app.set_status(f"ZBrush: nothing sent - failed: {type(exc).__name__}: {exc}")
            return False
        for _k, ident, _d, m in sends:
            self._manifests[_key(ident)] = [m]  # a send starts the history anew
        targets = len(sends) - 1
        extra = f"; {targets} morph target{'s' if targets != 1 else ''} as own SubTools" if targets else ""
        uv_text = "; UVs" if manifest.sent_uvs is not None else ""
        app.set_status(f"ZBrush: {obj.name!r} sent ({len(manifest.vertex_ids)} points{uv_text}{_ngon_text(manifest)}"
                       f"{extra})")
        return True

    def install(self) -> bool:
        try:
            folder = goz_install.install(self.paths(), self.inbox.directory)
        except (GozSetupError, OSError) as exc:
            self.app.set_status(f"ZBrush: {exc}")
            return False
        self.app.set_status(f"ZBrush: Mirai registered ({folder}) - restart ZBrush, then choose Mirai with R "
                            "beside the GoZ button")
        return True

    # -- return -------------------------------------------------------------------------------------------------------

    def tick(self) -> int:
        """Claim waiting tickets (at most every 0.25 s). Returns how many objects arrived."""
        now = self._clock()
        if now - self._last_poll < 0.8 * POLL_SECONDS:  # main.py schedules it every POLL_SECONDS (clock jitter)
            return 0
        self._last_poll = now
        arrived = 0
        try:
            tickets = self.inbox.waiting()
            for ticket in tickets:
                for received in self.inbox.claim(ticket) or ():
                    arrived += 1
                    if received.goz is None:
                        self.app.set_status(invalid_plan(received.identifier, received.error or "no file").summary())
                        continue
                    self._arrive(received.identifier, received.goz)
        except Exception as exc:  # runs in the window's clock: a bad transfer must never take the window down
            self.app.set_status(f"ZBrush: return failed: {type(exc).__name__}: {exc}")
        return arrived

    def _manifests_for(self, identifier: str) -> list[Manifest]:
        known = self._manifests.get(_key(identifier))
        if known:
            return known
        text = read_manifest_text(self.manifest_dir, identifier)  # D11: a ticket from before this Mirai started
        if text is None:
            return []
        try:
            return [Manifest.from_json(text)]
        except (ValueError, TypeError):
            return []

    def _plan_linked(self, identifier: str, goz: GozMesh,
                     texture: Optional[str] = None) -> tuple[ReturnPlan, Optional[Manifest]]:
        """The plan against the newest manifest version the object still matches (after an Undo of an apply: the one
        before it); a conflict only if it matches none."""
        versions = self._manifests_for(identifier)
        first: Optional[tuple[ReturnPlan, Optional[Manifest]]] = None
        for manifest in reversed(versions):
            plan = self.plan(identifier, goz, manifest, texture)
            if plan.kind is not ReturnKind.CONFLICT:
                return plan, manifest
            first = first or (plan, manifest)
        return first or (self.plan(identifier, goz, None, texture), None)

    def plan(self, identifier: str, goz: GozMesh, manifest: Optional[Manifest],
             texture: Optional[str] = None) -> ReturnPlan:
        from mirai.regions import new_group_name

        to_world, to_object = _placement()
        scene_path = self._scene_path()
        obj = None if manifest is None else self.app.scene.objects.get(ObjectId(manifest.object_id))
        return plan_return(
            goz, manifest, self.app.scene, identifier=identifier, session_id=self.session_id,
            scene_path=None if scene_path is None else str(Path(scene_path).resolve()),
            to_world=to_world, to_object=to_object, symmetry=None if obj is None else symmetry_info(obj.mesh),
            new_group_name=new_group_name, texture=texture,
        )

    def _copy_texture(self, goz: GozMesh, identifier: str) -> tuple[Optional[str], Optional[str]]:
        """P3b: the return's texture copied beside the scene (or into `goz/textures/`); (path, note)."""
        if not goz.texture_path:
            return None, None
        from interop.goz.texture import copy_texture, texture_dir

        source = Path(goz.texture_path)
        if not source.is_file():
            return None, f"texture {source.name} not found"
        known = self._manifests_for(identifier)
        name = known[-1].object_name if known else (
            goz.name[len("GoZMesh_"):] if goz.name.startswith("GoZMesh_") else goz.name)
        try:
            copy, note = copy_texture(source, texture_dir(self._scene_path(), self.texture_dir), name)
        except OSError as exc:
            return None, f"texture not copied: {exc}"
        return str(copy.resolve()), note

    def _arrive(self, identifier: str, goz: GozMesh) -> None:
        texture, note = self._copy_texture(goz, identifier)
        plan, manifest = self._plan_linked(identifier, goz, texture)
        if note:
            plan.notes.append(note)
        self.waiting = [w for w in self.waiting if not same_identifier(w.identifier, identifier)]  # newer supersedes
        if plan.in_place or plan.new_object:
            w = Waiting(identifier, goz, manifest, plan, texture)
            self.waiting.append(w)
            prefix = APPLY_PREFIX if plan.in_place else NEW_OBJECT_PREFIX
            self.app.set_status(f"{plan.summary()} - SPACE > {prefix + w.tag!r}")
        else:
            self.app.set_status(plan.summary())

    def confirm(self, w: Waiting) -> bool:
        plan, manifest = self._plan_linked(w.identifier, w.goz, w.texture)
        if plan.kind is not w.plan.kind:
            # the scene changed since the arrival: show the new verdict, apply nothing (the artist confirms again)
            w.plan = plan
            if not (plan.in_place or plan.new_object):
                self._forget(w)
            self.app.set_status(f"{plan.summary()} - changed since it arrived, nothing applied")
            return False
        siblings = self._sibling_shapes(manifest, w.identifier) if plan.in_place and manifest is not None else []
        done = self.app.apply_goz_return(plan)
        if done:
            self._forget(w)
            if plan.in_place and manifest is not None:
                self._rebase(manifest, plan)
                self._rebase_siblings(siblings, plan.object_id)
            if plan.new_object:
                self.app.set_status(f"{self.app.status_message} - it is selected now: {SEND_LABEL!r} sends it "
                                    "(leave mode 4 to send the edit object)")
        return done

    def _rebase(self, manifest: Manifest, plan: ReturnPlan) -> None:
        obj = self.app.scene.objects.get(plan.object_id)
        if obj is None:
            return
        to_world, _ = _placement()
        rebased = rebase_manifest(manifest, self.app.scene, obj, to_world, plan.goz.points, plan)
        versions = self._manifests.setdefault(_key(manifest.identifier), [])
        versions.append(rebased)
        del versions[:-32]
        try:
            write_manifest(self.manifest_dir, manifest.identifier, rebased.to_json())
        except OSError:
            pass  # the in-memory manifest is enough for this session

    def _sibling_shapes(self, manifest: Manifest, identifier: str) -> list[tuple[Manifest, list]]:
        """The other SubTools of the same object (P3c: base and targets) with what ZBrush holds of each, taken before
        an apply changes the object."""
        from interop.goz.bridge import sent_points, target_layer

        obj = self.app.scene.objects.get(ObjectId(manifest.object_id))
        if obj is None:
            return []
        to_world, _ = _placement()
        out = []
        for key, versions in self._manifests.items():
            if key == _key(identifier) or not versions or versions[-1].object_id != manifest.object_id:
                continue
            m = versions[-1]
            layer = target_layer(m)
            if layer is not None and layer not in obj.mesh.point_layer_ids():
                continue
            held = m.zbrush_points if m.zbrush_points is not None else sent_points(obj, to_world, layer)
            out.append((m, [tuple(p) for p in held]))
        return out

    def _rebase_siblings(self, siblings: list[tuple[Manifest, list]], object_id) -> None:
        from interop.goz.bridge import rebase_sibling

        obj = self.app.scene.objects.get(object_id)
        if obj is None:
            return
        to_world, _ = _placement()
        for m, held in siblings:
            rebased = rebase_sibling(m, self.app.scene, obj, to_world, held)
            versions = self._manifests.setdefault(_key(m.identifier), [])
            versions.append(rebased)
            del versions[:-32]

    def _forget(self, w: Waiting) -> None:
        self.waiting = [x for x in self.waiting if x is not w]


def _ngon_text(manifest: Manifest) -> str:
    stats = manifest.extra.get("ngon_split")
    if not stats:
        return ""
    text = f"; {stats['split']} n-gons split in the file"
    if "mirrored" in stats:
        text += f", {stats['mirrored']} mirror-symmetric"
        if stats["asymmetric"]:
            text += f", {stats['asymmetric']} not (no mirror partner or no valid symmetric split)"
    return text


def _key(identifier: str) -> str:
    import os

    return os.path.normcase(identifier.replace("\\", "/"))


__all__ = ["ZBrushBridge", "ReturnKind", "DEFAULT_INBOX"]
