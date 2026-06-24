# Data Sources & Provenance

All datasets are **git-ignored** (`data/` is excluded). Document every
source here so the pipeline is reproducible from scratch.

## Primary: air network (in use)

| Field | Value |
|-------|-------|
| Source | OpenFlights — <https://openflights.org/data.html> |
| Files | `airports.dat`, `routes.dat` |
| License | OpenFlights / ODbL-style; see their site, attribute on use |
| Nodes | Airports (filtered to Europe) |
| Edges | Routes; weight = flight frequency proxy |
| Notes | Static snapshot; no timetable/temporal info |

**Population proxy.** Airports have no population field, so we estimate it
from degree: `pop(v) = 150_000 + degree(v) * 45_000`. This is an
assumption (more routes ⇒ bigger city), not ground truth — flag it as a
limitation and consider replacing with real city population (e.g.
GeoNames / Eurostat) joined by airport→city.

## Planned: ground & sea layers (multimodal)

Adding boat and ground networks is feasible **and supported by published
work** — each modality has been studied as a transmission network in its
own right. They enter as additional edge layers over a shared node set
(cities/regions/ports). Each row below pairs a candidate data source with
the literature that validates using it for epidemic modelling.

Split each land layer into **topology** (the edges) and **flow weights**
(how many people move), because they have *different global coverage*.

| Layer | Topology source (global) | Flow-weight source | Supporting literature | Caveats |
|-------|--------------------------|--------------------|-----------------------|---------|
| Air (baseline) | OpenFlights (global) | route frequency | `colizza:airline`, `guimera:anomalous` | static snapshot |
| Rail | OSM `railway=*` (global) | gravity/radiation model | HSR↔COVID studies (lit-review §3b, *verify authors*) | needs station→city mapping |
| Road | OSM `highway=*`; **GRIP** `meijer:grip` (222 countries, global) | gravity/radiation model | `tizzoni:proxies` | full road graph huge → region-level |
| Sea / ferry & shipping | OSM `route=ferry`; cargo port-call data | port traffic | `kaluza:cargo`, `seebens:bioinvasion` | cargo/vector-borne, not direct human spread |

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
§ Multimodal and [`ROADMAP.md`](ROADMAP.md) for scoping this as a stretch
goal vs the core Europe/air result.

> **Disease-relevance caveat for shipping.** `kaluza:cargo` and
> `seebens:bioinvasion` model *cargo* ships, whose epidemic relevance is
> mainly vector/ballast-borne (cholera, invasive species) rather than
> direct person-to-person transmission. For a *human* respiratory-disease
> story, prioritise commuting/rail over cargo shipping; include sea mainly
> for islands and passenger ferries.

## Reproducing the data step

```bash
python -m src.retrieve.openflights        # MODULE 1 → data/raw/air/
python -m src.netgen.build --region europe --layers air \
    --out data/processed/europe/air.graphml   # MODULE 2: filter + weight + populate
```

Record the download date and any source version in
`data/raw/PROVENANCE.txt` (the data itself is not committed).
