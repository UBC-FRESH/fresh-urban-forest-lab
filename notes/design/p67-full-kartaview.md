# P67 full live-host KartaView pass

Parent issue: #324
Branch: `feature/p67-full-kartaview`
Status: active

## Goal

Process every decodable KartaView image on a live storage host, not the prior bounded
per-cell sample.

## Approach

- Query the same 118-cell 1 km grid.
- Exclude `storage1.openstreetcam.org` records whose blobs return 404.
- Select all remaining live-host records, with no per-cell cap.
- Download concurrently and process with OneFormer + ZoeDepth.
- Preserve earlier pilot and sample layers separately.
- Publish the full available layer with explicit coverage and failure accounting.

## Limits

- Still a KartaView image set, not a complete street census.
- FOV remains assumed at 60°.
- Imagery is predominantly 2016-2018; inventory is current.
- No precision, recall, field-validation, ownership, or survival claim.
