# Resume note — staged run interrupted

**Interrupted:** 2026-07-03 ~01:28 (killed cleanly to power off overnight).

## Where it stopped
- **Stage 4 (dose), disease `seiqrd`: 54 of 60 runs done** (6 remaining).
- Everything before it is **complete**:
  - Stage 1 (spread) — done
  - Stage 2 (defend) — done; **betweenness won all 5 diseases**
  - Stage 4 dose for `sir`, `sis`, `seir`, `seirs` — 60/60 each
- **Stage 5 (interdiction) — NOT started.**

## Data integrity
Clean kill between runs — **no partial/corrupt folders** (verified: every run dir
has summary.json + timeseries.parquet + state.npz). Nothing to delete.

## To resume (no reruns of finished work)
```
cd ~/Documents/GitHub/netsci-disease-spread
uv run netsci evaluate staged --config experiment.yaml --workers 10
```
`skip_existing` reuses all completed runs. Only the remaining ~6 `seiqrd` dose
runs + the full Stage 5 interdiction will actually compute (~30–60 min).

Then follow the runbook in `docs/RESEARCH-ROADMAP.md` (collect / structure /
viz figures / viz tables / pytest) to rebuild aggregates and update the paper.

_Delete this file once the run is finished._
