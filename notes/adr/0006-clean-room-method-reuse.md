# ADR 0006: Reimplement copyleft methods clean-room, never copy their code

Status: accepted
Date: 2026-11-03
Issues: #61, #62

## Context

The project needs stronger point-cloud conditioning and, later, individual-tree and QSM
methods. Arbor (`r-lidar/arbor`) is a strong MLS/TLS reference with a detailed book, but
it is GPL-3.0. This repository is MIT. Copying Arbor code, even a small helper, would make
the combined work copyleft and would break the licence posture recorded in
`notes/reference/software-landscape.md` and `AGENTS.md`.

The lab also wants to credit ideas properly. A reimplementation that quietly reproduces
another package's method without citation is not acceptable, even when the code is new.

## Decision

- Mine Arbor's **methods, algorithms, data contracts, and design patterns**, not its code.
- Write the implementation from the book, manual, and published papers, with our own
  structure, names, tests, and documentation.
- Do not copy Arbor R/C++ source into this repository, including vendored MIT components.
  Use a permissive Python dependency or a fresh implementation instead.
- Record provenance in three places for every mined method:
  1. a `Method provenance` section in the module/function docstring;
  2. a row in `notes/reference/arbor-method-mining.md`;
  3. a paragraph in `docs/reference/arbor-method-mining.rst`.
- Cite the underlying method paper where one exists, in addition to Arbor.
- Stop for an explicit licence review before any future change copies a code block rather
  than reimplements it.
- Keep mined functions opt-in until they have their own tests, docs, and a named
  uncertainty. Do not silently replace the existing CHM/ITD path.

## Consequences

- The implementation will be smaller and slower to write than a direct copy, but it keeps
  the MIT licence and the standalone-core rule.
- The provenance surface is larger: every method needs a docstring, a note row, and a docs
  paragraph. That is deliberate.
- Some Arbor internals are not documented deeply enough to reproduce exactly. The
  reimplementation may differ in edge cases. The note must say what was not verified.
- Future MLS/TLS/QSM work can reuse the same policy without reopening the licence
  question.

## Alternatives considered

- **Copy Arbor code and relicense the project.** Rejected: it breaks the MIT/standalone
  posture and the existing project rule.
- **Add Arbor as an R dependency through `rpy2` or a subprocess.** Rejected as a core
  dependency: it imports GPL code, adds an R runtime, and couples the release cadence to
  another lab system. A future optional adapter would still need a licence review.
- **Use only permissive libraries and skip Arbor entirely.** Rejected: the Arbor book
  contains useful method and design guidance that is not readily available elsewhere in
  this form.
- **Cite Arbor only in a top-level note.** Rejected: attribution that is not next to the
  code is easy to lose. The docstring, note, and Sphinx page are all required.
