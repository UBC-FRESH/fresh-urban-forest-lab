# Post-v0.5.0 housekeeping

Date: 2026-11-14.

Status: complete.

## Completed issues

Closed eight completed child issues whose parent phases were already closed:

- P53.1 #283, P53.2 #284, P53.3 #285
- P54.1 #289, P54.2 #290
- P55 #293
- P56.1 #300, P56.2 #301

Each issue received a close-out comment naming its parent and evidence report.

## Documentation corrections

- `docs/reference/limitations.rst` now names v0.5.0 instead of v0.3.0 and replaces the
  obsolete two-core-tile City limit with the citywide/P37 boundary.
- `docs/reference/project-status.rst` now names the v0.5.0 release and replaces the stale
  City-coverage gap with the current P37 and western-control caveats.
- `notes/README.md` now indexes the P38-P59 phase reports.

## Branch cleanup

- Deleted 25 local branch refs whose tips matched merged pull requests.
- Deleted stale merged remote branch refs and pruned remote-tracking refs.
- Kept active worktree branches `feature/p37-surrey-coquitlam-imagery` and
  `feature/p33-remove-ground-classifier`.
- Kept local and remote branches whose tips no longer matched their merged PR heads, and
  branches without a merged PR.

## Verification

- Open issues: 0.
- Open pull requests: 0.
- Worktrees: `main`, P37, and the arbor/P33 checkout.
- Public portal routes remained healthy.
- Dashboard: **GREEN**.
