# N-World Archaeology – Recovery of the Original Documentation

> Status: **active investigation**  
> Goal: recover and preserve the original N-World 3.0 documentation and use it as the primary technical reference for Mirai-Bastel.

## 1. The target

The historical N-World 3.0 Online Documentation is repeatedly cited by independent sources as:

`http://www.aaronjamesrogers.com/misc/nworld/N-World-Intro.html`

The current host times out, so the live URL is not presently usable.

Important: the URL itself is nevertheless independently corroborated as the N-World 3.0 documentation reference. HandWiki and other reproductions cite it directly. [1]

## 2. Strong new lead: archived N-World 3.2 software

A copy of **Nichimen N-World 3.2** is preserved on the Internet Archive:

https://archive.org/details/nichimen-n-world-3.2

This is potentially more valuable than a web page alone because the software itself may contain documentation, help files, examples, manuals, README files, or other assets from the original distribution.

A 2025 preservation discussion specifically identifies the archive and describes N-World as the difficult-to-find predecessor of Mirai. [2]

A separate preservation mirror/reproduction describes the archive as containing installation notes in `N-World readme.txt` and confirms Windows NT requirements. [3]

**Research action:** inspect the complete archive contents, especially:

- README / installation notes
- `.txt`, `.html`, `.htm`, `.hlp`, `.chm`, `.pdf` and documentation files
- example scenes/assets
- `worlds` directory
- executable/resource names that reveal module structure
- strings referring to commands, editors, selection, camera or modeling
- any sample scripts

## 3. Why the software archive matters

The N-World documentation may no longer be indexed by modern search engines, but historical software distributions often contain documentation that was never separately archived.

Therefore we should treat the software archive as a **documentary artifact**, not merely something to run.

Potential workflow:

```text
N-World 3.2 archive
        ↓
inventory every file
        ↓
identify documentation/help/resources
        ↓
extract text / screenshots where appropriate
        ↓
compare with contemporary magazine descriptions
        ↓
reconstruct actual systems
```

## 4. Historical evidence already recovered

Independent references identify N-World as a Common Lisp 3D graphics package from Nichimen, with N-Geometry, N-Dynamics, N-Render and N-Paint components. N-Geometry included smoothing, magnet geometry editing and instancing; N-Dynamics included scripting, curve-based animation and skeletal animation. [1]

This is useful as a high-level map, but **not sufficient for implementation**. The original documentation remains the target.

## 5. Mirai/N-World preservation community

A current preservation thread confirms that N-World 3.2 is rare and that preservationists have actively tried to get it running on Windows NT/VirtualBox. The same discussion links the Internet Archive copy. [2]

A WinWorld discussion also records a 2021 user offering `Nichimen_N-World_3.2.zip`, and later links the Internet Archive copy. [4]

These are secondary sources, but useful for locating surviving artifacts and installation information.

## 6. Important caution

Do **not** treat modern forum claims as authoritative technical documentation.

For example, users describe Mirai as a "3D operating system" and discuss its Common Lisp architecture. These observations are valuable clues, but we should distinguish:

- what the original software/documentation explicitly says;
- what a contemporary professional review reports;
- what a later user remembers;
- what we infer from observed behavior.

## 7. Search targets

The following should be investigated systematically:

### Original documentation

- N-World 3.0 Online Documentation
- N-World 3.1 documentation
- N-World 3.2 documentation
- Mirai 1.x manuals/help
- Nendo 1.x manuals/help

### Web archives

- Wayback snapshots of `aaronjamesrogers.com/misc/nworld/`
- snapshots of individual documentation pages
- archived directory structures
- cached mirrors of images referenced by the manual

### Software archives

- Internet Archive N-World 3.2
- Internet Archive Mirai 1.1a
- WinWorld archives
- old SGI/IRIX distributions

### Search terms

- `N-World 3.0 Online Documentation`
- `N-World-Intro.html`
- `N-Geometry`
- `N-Dynamics`
- `N-World Selection`
- `N-World modeling`
- `N-World camera`
- `N-World magnet`
- `N-World winged edge`
- `Nichimen N-World manual`

## 8. Current conclusion

**We have not recovered the original HTML manual yet.**

But we now have a much stronger route to it than before:

1. The exact original URL is independently corroborated.
2. The historical host is confirmed dead/unreachable.
3. A surviving N-World 3.2 software archive exists.
4. Preservationists have recently demonstrated interest in recovering and running N-World.
5. The software distribution itself is now a promising source for embedded documentation.

### Next excavation step

**Download/inventory the N-World 3.2 archive and inspect it for documentation and help assets.**

That should happen before we make any further architectural assumptions about the N-World/Mirai system.

## Sources

[1] HandWiki – Software:N-World, including the explicit reference to “N-World 3.0 Online Documentation”.
https://handwiki.org/wiki/Software%3AN-World

[2] Reddit / Lisp preservation discussion – N-World 3.2 archive and recovery efforts.
https://www.reddit.com/r/lisp/comments/1iqeg1v

[3] EVBN reproduction of Internet Archive N-World 3.2 description, including installation notes and Windows NT observations.
https://evbn.org/nichimen-nworld-32-nichimen-graphics-free-download-borrow-and-streaming-internet-archive-1680182838/

[4] WinWorld – Request: Mirai and Nendo, including surviving N-World 3.2 references.
https://forum.winworldpc.com/discussion/12264/request-mirai-and-nendo
