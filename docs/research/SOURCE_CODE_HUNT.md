# Mirai / N-World Source-Code Hunt 🤠🧐

This is the forensic research log for locating surviving implementation material from Symbolics S-Graphics, Nichimen N-World, and Izware Mirai.

## Current conclusion

No verified public source tree for the original Nichimen N-World or Izware Mirai has been found so far. Current evidence instead points to preserved binaries/distributions, documentation, developer interviews, and Lisp runtime metadata as the most promising surviving technical material.

This is **not** evidence that source code never survived; only that no trustworthy public copy has been located yet.

## Major new lead: Franz / Allegro CL

Franz's historical customer case for Nichimen is one of the most valuable technical sources found so far:

- https://franz.com/success/customer_apps/animation_graphics/nichimen.lhtml
- PDF version: https://franz.com/success/customer_apps/animation_graphics/nichimen.app.pdf

Bob Coyne, Nichimen's Director of Software Development, describes N-World as a very large Common Lisp/CLOS system built with Allegro CL. The case study specifically mentions:

- dynamic linking
- incremental compilation
- macros
- automatic memory management
- debugger/backtrace support
- source locators
- `apropos`
- `arglist` information
- `who-calls` information
- an interpreter
- Allegro CL Meta-Object Protocol (MOP)
- application-specific semantics layered onto CLOS
- deployment metadata that allowed developers to inspect objects and application state even without source code
- using this runtime/introspection machinery to **update the application**

This is enormously important for our architectural reconstruction. It suggests that N-World's extensibility was not merely an external scripting layer: the Lisp/CLOS runtime itself was deeply integrated with the application and development workflow.

## Particularly important quote / observation

Franz reports that N-World used deployment metadata to examine objects, obtain meaningful backtraces and function arguments, and generally explore application context. Coyne also says that incremental compilation made it practical to experiment with unfamiliar code and learn how a large system worked.

For Mirai-Bastel this raises a major research question:

> Did the famous Mirai "everything remains live and editable" workflow partly emerge from the same live-object / incremental-development architecture?

We must **not** assume the answer yet, but this is now a high-priority hypothesis to investigate.

## Domain-specific language / macros

Franz also has a 1997 article on Allegro CL/CLOS and domain-specific languages:

- https://franz.com/support/tutorials/closanddsl.lhtml

It explicitly lists Nichimen's N-World as an example of an application-specific language built on Common Lisp/CLOS.

This is relevant because the historical Mirai/N-World interface may have been easier to implement as a highly declarative, context-sensitive system than a conventional C++-style command/tool architecture.

## S-Geometry lineage

A preserved 1988 S-Geometry manual is discussed and linked from the Lisp community:

- https://www.reddit.com/r/lisp/comments/1f5o06r/symbolics-s-geometry-manual-1988/

The quoted manual introduction describes S-Geometry as an integrated 3D database/editor with:

- polygonal objects
- geometric and topological operations
- vertex, edge and face interaction
- orthographic and perspective views
- interactive point-of-view control
- smooth manipulation in 3D
- a direct interface between the editor and underlying database

This is a crucial predecessor to N-World/Mirai and should be treated as an architectural ancestor, not merely historical trivia.

A technical paper independently describes S-Geometry as completely implemented in Symbolics Common Lisp and says its object structures contained face, edge and vertex information in rings. Source:

- https://citeseerx.ist.psu.edu/document?doi=b89413dddde1258a02593c4adb25be638fe3480c&repid=rep1&type=pdf

This provides unusually strong evidence for the historical data-model lineage.

## N-World preservation lead

A 2025 preservation effort reports that the current owner of the company that absorbed Izware no longer had a copy of N-World, while a working N-World 3.2 archive exists at Internet Archive:

- https://archive.org/details/nichimen-n-world-3.2

The preservation discussion:

- https://www.reddit.com/r/lisp/comments/1iqeg1v/back-again-now-for-the-classic-3d-n-world-software/

This makes the Internet Archive distribution especially important. It should be examined not only as executable software but as a **historical distribution containing documentation, configuration, scripts, resources and possibly runtime artifacts**.

## N-World 3.2 file-level clues

A preservation discussion reproduces installation notes referring to:

- `setup.exe`
- `obj/libp32.dll`
- `worlds/*.dxl`
- `nwcrk.zip`
- `NWCRK.EXE`

The `*.dxl` files and Lisp-related runtime components are worth investigating. We do **not** currently know what proprietary format/function these files contain. They should be treated as forensic artifacts, not assumed to be source.

## Other historical evidence

A 1998 Common Lisp discussion identifies Nichimen's products as Lisp-based and describes N-World as the flagship successor to earlier Symbolics-derived graphics work:

- https://groups.google.com/g/comp.lang.lisp/c/SA1d2_Hz3t4

Another contemporary Lisp discussion from around 2000 states that Mirai was mostly written in Allegro Common Lisp and identifies its Symbolics S-Graphics ancestry:

- https://groups.google.com/g/comp.lang.lisp/c/r6V4sBCTqWw

These are community/Usenet sources, so they are supporting evidence rather than primary documentation.

## Important distinction: S-Graphics vs N-World vs Mirai

Do not collapse these systems into one implementation.

Current working model:

```text
Symbolics S-Graphics
        │
        │  original Lisp-machine system
        ↓
port / continuation / development
        ↓
Nichimen N-World
        │
        │  Allegro CL + CLOS + Nichimen-specific extensions
        ↓
Izware / Nichimen Mirai
```

The exact amount of code and architecture carried forward at each transition remains an open research question.

A 2017 IRIX preservation discussion claims that significant N-World development was done at Triple-I, including the port from Symbolics to SGI, and that Franz contributed to the Allegro CL implementation. This is useful historical evidence but is currently **unverified secondary testimony**:

- https://nekonomicon.irixnet.org/forum/11/16731536/1.html

## Search strategy

Do not search only for `Mirai source code`.

Search by artifact and ancestry:

### Product names

- `N-World`
- `NWorld`
- `N-World 3`
- `Mirai`
- `Mirai 1.1`
- `Nichimen Graphics`
- `Winged Edge Software`
- `Izware`

### Ancestors

- `S-Graphics`
- `S-Geometry`
- `S-Dynamics`
- `S-Render`
- `Symbolics Graphics Division`
- `Nichimen Symbolics`

### Implementation technology

- `Allegro CL`
- `Common Lisp`
- `CLOS`
- `MOP`
- `ZetaLisp`
- `CLX`
- `Triple-I`

### File/artifact terms

- `*.lisp`
- `*.lsp`
- `*.fasl`
- `*.fas`
- `*.dxl`
- `libp32.dll`
- `worlds`
- `README`
- `developer`
- `source`
- `SDK`
- `examples`
- `macros`

### People

Search former developers and technical staff individually rather than relying only on product names. In particular, follow names appearing in Franz/Nichimen material and historical S-Graphics documentation.

## What would count as a major source-code discovery?

### Level A — actual source

- original `.lisp` / `.lsp` source
- source repository
- source archive
- developer backup containing substantial source

### Level B — executable Lisp internals

- Lisp images with symbols/classes/methods retained
- readable runtime metadata
- development images
- dumped Lisp images
- object/class names sufficient to reconstruct architecture

### Level C — scripts and examples

- modeling scripts
- macros
- menu definitions
- application extensions
- example programs
- file-format scripts

### Level D — binaries and resources

- N-World/Mirai binaries
- help systems
- DLLs
- resource files
- proprietary data formats

These can still reveal architecture through strings, symbols, file formats and behavior, but should not be mistaken for source.

## Legal / repository policy

If original proprietary source is found, **do not copy it into Mirai-Bastel merely because it is publicly downloadable**.

Instead record:

- source URL / archive
- version
- date
- provenance
- checksum where useful
- known license/copyright status
- what was learned from it

Use it as a research reference and implement independent code for Mirai-Bastel.

## Current high-priority tasks

1. Inspect every file in the N-World 3.2 Internet Archive distribution.
2. Determine what `*.dxl` files actually are.
3. Look for help files, scripts, examples and developer/runtime artifacts.
4. Search historical web archives for the original N-World 3.0 documentation.
5. Search for preserved S-Geometry documentation and examples.
6. Identify N-World/Mirai developers and search their public/archived work.
7. Investigate whether Allegro CL images or development environments survived.
8. Investigate the exact relationship between the N-World runtime metadata/MOP and the integrated editor workflow.

## Status

**Source code:** not found.

**Very strong architectural evidence:** found.

**Preserved executable N-World distribution:** found.

**Preserved Mirai distribution:** found.

**Original S-Geometry documentation:** strong evidence of surviving manual material.

**Best current lead:** N-World 3.2 distribution + Franz's technical description of the live Allegro CL/CLOS architecture.
