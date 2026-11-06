"""Mirai <-> ZBrush over GoZ in the SPACE menu (AD-029, P1, `PROVISIONAL`; like `src/obj_files.py`: no pyglet).

Rows (no key: a key only after Manu's "Taste passt", AD-013 addendum):

    An ZBrush senden                     the object (mode 4: the one selected object, else the edit object; the base
                                         while a morph target's view is open) -> ZBrush, as `(x, -y, -z)` of its
                                         world position; a resend of the same object updates the same SubTool,
                                         also after a Mirai or ZBrush restart: Mirai names it itself
                                         (`interop.goz.names`, `goz/manifests/names.json`), no GoZMakeObjectPath
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
from interop.goz.names import REGISTRY_FILE, NameEntry, NameRegistry, scene_key, stem_of, with_stem
from interop.goz.transfer import (
    Inbox,
    default_runner,
    launch_zbrush,
    launch_zbrush_with_script,
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
        self._process_id = uuid.uuid4().hex
        #: Mirai's own SubTool names (per scene file / session, object and target), kept beside the manifests
        self.names = NameRegistry(self.manifest_dir / REGISTRY_FILE)
        #: per identifier the manifest versions of this session, oldest first: the send, then one per applied return,
        #: so a return after an Undo of an apply links to the version the object is back at (no resend needed)
        self._manifests: dict[str, list[Manifest]] = {}
        self.waiting: list[Waiting] = []
        self._rows: dict[str, tuple[str, Waiting]] = {}

    @property
    def session_id(self) -> str:
        """This Mirai process and the scene it holds: loading another scene is another session, so object IDs that
        repeat in the loaded file never link to a send of the scene before (AD-029 §5)."""
        return f"{self._process_id}.{getattr(self.app, 'scene_generation', 0)}"

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
            project = paths.project_dir()
            self.names.reload()
            sends = []  # (key, identifier, data, manifest): the base first, then each morph target (P3c)
            for layer in [None, *morph_target_ids(obj.mesh)]:
                key = (obj.id, None if layer is None else int(layer))
                title = obj.name if layer is None else f"{obj.name}_{obj.mesh.point_layer_info(layer).name}"
                entry = self.names.allocate(
                    short_name(title), scene=scene_key(scene_path), session=self.session_id, object_id=int(obj.id),
                    layer=key[1], foreign_file=lambda stem: (project / f"{stem}.GoZ").exists(),
                    legacy=lambda stem: self._legacy_entry(project, stem),
                    dead=lambda e: self._is_dead(e, scene_key(scene_path)))
                identifier = str(project / entry.stem)
                data, manifest = build_send(
                    app.scene, obj, identifier=identifier, transfer_id=transfer_id, session_id=self.session_id,
                    scene_path=None if scene_path is None else str(Path(scene_path).resolve()), to_world=to_world,
                    triangulate=_triangulate(), symmetry=symmetry_info(obj.mesh), layer=layer,
                )
                sends.append((key, identifier, data, manifest))
            for _key_, identifier, _data, manifest in sends:
                write_manifest(self.manifest_dir, identifier, manifest.to_json())
            self.names.save()
            _k, identifier, data, manifest = sends[0]
            write_send(paths, identifier, data, [(i, d) for _k2, i, d, _m in sends[1:]])
            if len(sends) > 1:
                launch_zbrush_with_script(
                    paths, [i for _, i, _, _ in sends], self.manifest_dir, runner=self._runner
                )
            else:
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
        tool = _short(identifier)
        as_text = f" as {tool!r}" if tool != short_name(obj.name) else ""
        app.set_status(f"ZBrush: {obj.name!r} sent{as_text} ({len(manifest.vertex_ids)} points{uv_text}"
                       f"{_ngon_text(manifest)}{extra})")
        return True

    def _is_dead(self, entry: NameEntry, scene: Optional[str]) -> bool:
        """A name of the current scene file (or this session) whose object or morph target is gone: its stem is free."""
        if not ((scene is not None and entry.scene == scene) or entry.session == self.session_id):
            return False
        obj = self.app.scene.objects.get(ObjectId(entry.object_id))
        return obj is None or (entry.layer is not None and entry.layer not in {int(x) for x in obj.mesh.point_layer_ids()})

    def _legacy_entry(self, project: Path, stem: str) -> Optional[NameEntry]:
        """A stem a Mirai before the name registry sent (its manifest is on disk): Mirai's, for the manifest's object."""
        from interop.goz.bridge import target_layer

        text = read_manifest_text(self.manifest_dir, str(project / stem))
        if text is None:
            return None
        try:
            m = Manifest.from_json(text)
        except (ValueError, TypeError):
            return NameEntry(stem=stem, title="", scene=None, session="", object_id=-1, layer=None)  # never taken over
        layer = target_layer(m)
        return NameEntry(stem=stem, title=stem, scene=scene_key(m.scene_path), session=m.session_id,
                         object_id=m.object_id, layer=None if layer is None else int(layer), updated=m.sent_at)

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

    def _disk_manifest(self, identifier: str) -> Optional[Manifest]:
        text = read_manifest_text(self.manifest_dir, identifier)  # D11: also a send of an earlier Mirai start
        if text is None:
            return None
        try:
            return Manifest.from_json(text)
        except (ValueError, TypeError):
            return None

    def _manifests_for(self, identifier: str) -> list[Manifest]:
        """This session's versions of the identifier, else the manifest on disk. The disk is the truth of who sent
        under a name last: if another Mirai (window) sent there since, ZBrush's Tool holds that send, and this
        session's versions are stale."""
        known = self._manifests.get(_key(identifier))
        disk = self._disk_manifest(identifier)
        if known and (disk is None or any(m.transfer_id == disk.transfer_id for m in known)):
            return known
        return [disk] if disk is not None else []

    def _resolve(self, identifier: str, goz: GozMesh) -> tuple[list[Manifest], Optional[str]]:
        """The manifest versions a return links to, and the name it was sent under if ZBrush renamed it."""
        versions = self._manifests_for(identifier)
        if versions:
            return versions, None
        return self._link_by_topology(identifier, goz)

    def _plan_linked(self, identifier: str, goz: GozMesh,
                     texture: Optional[str] = None) -> tuple[ReturnPlan, Optional[Manifest]]:
        versions, renamed_from = self._resolve(identifier, goz)
        return self._plan_versions(identifier, goz, versions, renamed_from, texture)

    def _plan_versions(self, identifier: str, goz: GozMesh, versions: list[Manifest], renamed_from: Optional[str],
                       texture: Optional[str]) -> tuple[ReturnPlan, Optional[Manifest]]:
        """The plan against the newest manifest version the object still matches (after an Undo of an apply: the one
        before it); a conflict only if it matches none."""
        first: Optional[tuple[ReturnPlan, Optional[Manifest]]] = None
        for manifest in reversed(versions):
            plan = self.plan(identifier, goz, manifest, texture)
            if renamed_from is not None:
                plan.notes.insert(0, f"linked by topology: ZBrush renamed {_short(renamed_from)!r} to "
                                     f"{_short(identifier)!r}, the next send goes there")
            if plan.kind is not ReturnKind.CONFLICT:
                return plan, manifest
            first = first or (plan, manifest)
        return first or (self.plan(identifier, goz, None, texture), None)

    def _topology_candidates(self, identifier: str) -> list[list[Manifest]]:
        """This session's manifest histories, and - after a Mirai restart - the newest manifest on disk of every
        name the registry holds for the current scene file (or this session)."""
        out, seen, keys = [], set(), set()
        scene = scene_key(self._scene_path())
        for key, versions in self._manifests.items():
            keys.add(key)
            if not versions or id(versions) in seen:
                continue
            seen.add(id(versions))
            m = versions[-1]
            if m.session_id == self.session_id or (scene is not None and scene_key(m.scene_path) == scene):
                out.append(versions)
        self.names.reload()
        for entry in self.names.entries:
            if not ((scene is not None and entry.scene == scene) or entry.session == self.session_id):
                continue
            other = with_stem(identifier, entry.stem)
            if _key(other) in keys:
                continue
            keys.add(_key(other))
            m = self._disk_manifest(other)
            if m is not None:
                out.append([m])
        return out

    def _link_by_topology(self, identifier: str, goz: GozMesh) -> tuple[list[Manifest], Optional[str]]:
        """A return under a name Mirai never sent (Manu 2026-11-06: ZBrush appends a number when a Tool of that name
        exists already): the SubTool of this session (or of the current scene file, from disk) with exactly the same
        topology; among several (an object's base and its targets, duplicated objects) the one whose last known ZBrush
        shape most points equal bit for bit, only if that best one is unique. The new name then becomes an alias of it
        (in memory and on disk) and the registry follows it, so the next send updates that Tool. ([], None) = no
        link."""
        from interop.goz.bridge import sent_points, target_layer

        faces = [list(f) for f in goz.faces]
        to_world, _ = _placement()
        scored = []
        for versions in self._topology_candidates(identifier):
            m = versions[-1]
            if len(m.vertex_ids) != len(goz.points) or m.faces != faces:
                continue
            obj = self.app.scene.objects.get(ObjectId(m.object_id))
            layer = target_layer(m)
            if obj is None or (layer is not None and layer not in obj.mesh.point_layer_ids()):
                continue
            held = m.zbrush_points if m.zbrush_points is not None else sent_points(obj, to_world, layer)
            same = sum(1 for a, b in zip(held, goz.points) if tuple(a) == tuple(b))
            scored.append((same, versions))
        if not scored:
            return [], None
        scored.sort(key=lambda x: -x[0])
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            return [], None
        versions = scored[0][1]
        sent_as = versions[-1].identifier
        self._manifests.setdefault(_key(sent_as), versions)
        self._manifests[_key(identifier)] = versions  # the same list: rebases of either name land in both
        entry = self.names.owner(stem_of(sent_as))
        try:
            write_manifest(self.manifest_dir, identifier, versions[-1].to_json())  # a later Mirai start finds it
            if entry is not None:
                self.names.follow(entry, stem_of(identifier))
                self.names.save()
        except OSError:
            pass  # the link holds for this session
        return versions, sent_as

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

    def _copy_texture(self, goz: GozMesh, known: list[Manifest]) -> tuple[Optional[str], Optional[str]]:
        """P3b: the return's texture copied beside the scene (or into `goz/textures/`) under the linked object's name;
        (path, note)."""
        if not goz.texture_path:
            return None, None
        from interop.goz.texture import copy_texture, texture_dir

        source = Path(goz.texture_path)
        if not source.is_file():
            return None, f"texture {source.name} not found"
        name = known[-1].object_name if known else (
            goz.name[len("GoZMesh_"):] if goz.name.startswith("GoZMesh_") else goz.name)
        try:
            copy, note = copy_texture(source, texture_dir(self._scene_path(), self.texture_dir), name)
        except OSError as exc:
            return None, f"texture not copied: {exc}"
        return str(copy.resolve()), note

    def _arrive(self, identifier: str, goz: GozMesh) -> None:
        versions, renamed_from = self._resolve(identifier, goz)
        texture, note = self._copy_texture(goz, versions)
        plan, manifest = self._plan_versions(identifier, goz, versions, renamed_from, texture)
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
            if not same_identifier(plan.identifier, manifest.identifier):  # a renamed Tool: its own name too
                write_manifest(self.manifest_dir, plan.identifier, rebased.to_json())
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
        own = self._manifests.get(_key(identifier))
        out = []
        seen = {id(own)}
        for versions in self._manifests.values():  # a renamed Tool is an alias of the same list: count each list once
            if id(versions) in seen or not versions or versions[-1].object_id != manifest.object_id:
                continue
            seen.add(id(versions))
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


def _short(identifier: str) -> str:
    return identifier.replace("\\", "/").rsplit("/", 1)[-1]


def _key(identifier: str) -> str:
    import os

    return os.path.normcase(identifier.replace("\\", "/"))


__all__ = ["ZBrushBridge", "ReturnKind", "DEFAULT_INBOX"]
