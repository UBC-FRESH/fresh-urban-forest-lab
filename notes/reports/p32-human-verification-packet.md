# P32 human verification packet

Built: 2026-11-06

Location:

- Directory: `data/processed/vancouver_2022/human_verification_packet/`
- ZIP: `data/processed/vancouver_2022/human_verification_packet.zip`
- Entry point: `index.html`

Contents:

- `index.html` — blind review UI for all 300 crops.
- `images/` — 300 centre-cropped orthophoto PNGs.
- `review_template.csv` — candidate ID, blank human_label, blank notes.
- `candidate_metadata.csv` — prior AI label, confidence, land proxy, height, crown
  radius, local area. Reviewers should not open this until after the first pass.
- `README.md` — instructions and source note.

The UI:

- shows the candidate ID and crop only by default;
- hides the prior AI label;
- has Tree / Non-tree / Uncertain buttons and optional notes;
- saves labels in browser local storage;
- shows progress and label counts;
- filters all / unlabeled / each label;
- exports `p32_human_labels.csv`;
- imports a CSV;
- supports printing with a print stylesheet.

The crop images come from the Data For Canada PMTiles mirror of the City of Vancouver
2022 7.5 cm orthophoto. No owner, address, or parcel-level ownership data is included.

This is a visual verification packet, not a field census. The labels remain unverified
until an independent reviewer completes the packet and the resulting CSV is scored against
the prior labels.
