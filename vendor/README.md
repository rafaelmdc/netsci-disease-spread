# Vendored data snapshots

Tracked, pre-built data so a clean clone runs end-to-end without depending on a
flaky live API.

## `ferries_world.json`

A global dump of OSM ferry ways (`route=ferry`, passenger), each kept as its
two terminal coordinates, filtered to crossings ≥ 5 km. Source: Overpass API,
licensed **ODbL** (© OpenStreetMap contributors).

This is the **default** source for the water layer: `netsci retrieve ferries`
copies this file into `data/raw/water/` instead of sweeping Overpass (which is
slow, rate-limited, and non-reproducible — see `src/retrieve/osm_ferries.py`).

### Refreshing the snapshot

To rebuild it from a live Overpass sweep (≈ several minutes, network required)
and re-vendor the result:

```bash
netsci retrieve ferries --force      # writes data/raw/water/ferries_world.json
cp data/raw/water/ferries_world.json vendor/ferries_world.json
```
