# Data Sources & Provenance

All raw datasets are **git-ignored** (`data/` is excluded) and rebuilt by the
pipeline — the one exception is the vendored ferry snapshot
(`vendor/ferries_world.json`, see end of this doc). Document every source here
so the pipeline is reproducible from scratch.

## Primary: air network (in use)

| Field | Value |
|-------|-------|
| Source | OpenFlights — <https://openflights.org/data.html> |
| Files | `airports.dat`, `routes.dat` |
| License | OpenFlights / ODbL-style; see their site, attribute on use |
| Nodes | **GeoNames cities** that airports map onto (see node identity below) |
| Edges | Routes; weight = flight frequency proxy |
| Notes | Static snapshot; no timetable/temporal info |

**Population is real, not a proxy.** Nodes are GeoNames cities
(**cities1000**: >1k population plus admin seats), so each node carries a
**real** population. Airports map onto the city they serve (next section). The
degree-based `pop(v) = p0 + degree(v)·p_route` in `experiment.yaml` is only a
*fallback* for the rare node that still lacks a real population — not the
default. (Earlier versions keyed nodes by airport and estimated population from
degree; that was replaced.)

## Ground & sea layers (multimodal)

Boat and ground networks enter as additional edge layers over a shared node
set (cities/regions/ports), **supported by published work** — each modality has
been studied as a transmission network in its own right. Each row below pairs a
data source with the literature that validates using it for epidemic modelling.

Split each land layer into **topology** (the edges) and **flow weights**
(how many people move), because they have *different global coverage*.

| Layer | Topology source (global) | Flow-weight source | Supporting literature | Caveats |
|-------|--------------------------|--------------------|-----------------------|---------|
| Air (baseline) | OpenFlights (global) | route frequency | `colizza:airline`, `guimera:anomalous` | static snapshot |
| Rail | OSM `railway=*` (global) | gravity/radiation model | HSR↔COVID studies (lit-review §3b) | needs station→city mapping |
| Road | OSM `highway=*`; **GRIP** `meijer:grip` (222 countries, global) | gravity/radiation model | `tizzoni:proxies` | full road graph huge → region-level |
| Sea / ferry & shipping | OSM `route=ferry` (via Overpass; **vendored snapshot**, see below); cargo port-call data | port traffic | `kaluza:cargo`, `seebens:bioinvasion` | cargo/vector-borne, not direct human spread |

### Flow weights: one model everywhere, Eurostat to validate

**Critical for the cross-region comparison.** Rail/road *topology* is
global (OSM, GRIP `meijer:grip`), but *commuting flow* data is not: Eurostat
covers Europe only. We must **not** use Eurostat for Europe and a model
elsewhere — region differences would then reflect the data source, not the
topology, invalidating the degree–betweenness comparison. So:

- Generate land-flow weights with a **single gravity/radiation model**
  (`simini:radiation`) calibrated on node population, applied **uniformly to
  every region** (Europe included). This is the GLEAM approach
  (`balcan:gleam`).
- Use **Eurostat commuting data only to *validate*** that model within
  Europe (does the model reproduce observed flows where we can check?).
  This is a strength: it gives the synthetic flows an empirical anchor
  without breaking cross-region comparability.

See [`METHODOLOGY.md`](METHODOLOGY.md) § "Comparison-axis consistency".

**Node identity.** Layers share a node set keyed by **city/place** (real
GeoNames cities, **cities1000**: >1k pop plus admin seats, so small towns and
islands have a real node). Airports and ferry terminals map onto the city they
*serve* by two routes, in order of authority:

1. **Curated served-city (air).** OpenFlights records a human-curated served
   *city* per airport ("London" for all five London airports); we resolve that
   name to a GeoNames node (name + multilingual alternate names, disambiguating
   same-name cities by proximity, rejecting hits >150 km). This is ground-truth
   data, not inference, and covers **~93 % of air traffic**.
2. **Gravity catchment basin (fallback + ferries).** When no served city is
   given (OSM ferry terminals) or the curated name doesn't resolve, we fall
   back to geometry: within a 60 km basin pick the city maximising
   `population / max(distance, 10 km)` — GLEAM's airport-basin idea (Balcan &
   Vespignani 2009).

**Known limitation (deliberate, conservative).** Airports/terminals whose
served place has *no* real GeoNames city within the basin (remote islands
below the 1k floor) are **dropped, not given a proxy population**. A fabricated
population is not inert: it would seed, transmit and diffuse during the
simulation, silently driving the dynamics. Keeping every node a *real,
populated* place is the more defensible choice. The cost is small and
documented: ~7.6% of airports but only **0–5% of regional air traffic**
(europe 0.3%, americas 2.5%, **oceania 5.3%**), and ~6% of ferry routes. This
under-represents remote-island connectivity — a conservative bias, not an
inflation. `scripts/validate_snap.py` reports the dropped share per region.

Both make all five London airports collapse onto *London*. Plain nearest-city
snapping does **not**: it put Heathrow on a 63k-pop village and gave the real
London node zero air traffic, which would corrupt the degree↔betweenness
analysis. We validate the mapping against OpenFlights' independent labels —
see `scripts/validate_snap.py` (coverage, geometric sanity, hub aggregation).
Every layer then contributes edges between these shared places. See
[`ARCHITECTURE.md`](ARCHITECTURE.md) § "Stack & node identity".

**Modelling note.** Air, rail/road, and sea operate at *different time and
distance scales*. The literature-backed way to combine them is a
**multilayer / multiplex metapopulation network** with layer-specific
travel rates, exactly as `balcan:multiscale` couples long-range air with
short-range commuting, and as `tizzoni:proxies` warns: the choice of
mobility layer materially changes the predicted spread. A key multilayer
result is that **coupling can push the system over the epidemic threshold
even when no single layer would sustain the outbreak alone** — so keep
layers tagged (each with its own migration rate), never merge them into
one undifferentiated edge set. See [`literature-review.md`](literature-review.md)
§ Multimodal for the supporting references.

> **Disease-relevance caveat for shipping.** `kaluza:cargo` and
> `seebens:bioinvasion` model *cargo* ships, whose epidemic relevance is
> mainly vector/ballast-borne (cholera, invasive species) rather than
> direct person-to-person transmission. For a *human* respiratory-disease
> story, prioritise commuting/rail over cargo shipping; include sea mainly
> for islands and passenger ferries.

## Reproducing the data step

`make run` (the one-command pipeline) runs `netsci retrieve all` as its first
stage, so you rarely call these directly. Each fetcher is **idempotent** — it
skips a source that is already present, so reruns are free and offline:

```bash
netsci retrieve openflights               # MODULE 1 → data/raw/air/      (~3 MB, network)
netsci retrieve geonames                  # cities1000 → data/raw/geonames/ (~30 MB, network)
netsci retrieve ferries                   # OSM ferry routes → data/raw/water/ (vendored, offline)
netsci netgen build-all                   # MODULE 2: every network in experiment.yaml
# or one network:  netsci netgen build --region europe --layers air
# force a fresh download of any source:   netsci retrieve <source> --force
```

Record the download date and any source version in
`data/raw/<layer>/PROVENANCE.txt`. The raw data itself is **not** committed
(`data/` is git-ignored), with one deliberate exception below.

### Vendored ferry snapshot (`vendor/ferries_world.json`)

A live ferry build sweeps a global grid of OpenStreetMap `route=ferry` ways via
the public Overpass API — slow (several minutes), rate-limited, and
**non-reproducible** (cells time out and are skipped: 54/63 on the snapshot
run). To keep a clean-clone run deterministic and offline, the resulting dump
(~370 KB, 3294 crossings ≥ 5 km, ODbL) is committed at `vendor/ferries_world.json`
and baked into the Docker image. `netsci retrieve ferries` resolves in order:

1. `data/raw/water/ferries_world.json` already present → use it;
2. else the vendored snapshot → copy it in (the default; **no network**);
3. else (or `--force`) → a live Overpass sweep, hardened with retries and
   mirror endpoints.

Refresh the snapshot with `netsci retrieve ferries --force` and re-copy the
result into `vendor/` (see `vendor/README.md`).
