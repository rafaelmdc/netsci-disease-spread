# Literature Review — Disease Spread on Networks

Annotated reading guide for the project. Organised by theme, roughly
old → recent within each. BibTeX keys match
[`tex/references.bib`](tex/references.bib). Use this both to write Related
Work and to locate the gap our project fills (see
[§ Where we fit](#where-we-fit-the-novelty-argument)).

> **Reliability note.** Every entry below was verified against a primary
> source except where marked **⚠ UNVERIFIED**. Do not cite unverified
> entries until the full reference is confirmed.

---

## 1. Foundations of network science

- **Watts & Strogatz (1998), *Nature* — small-world networks.**
  `watts:smallworld`. Short path lengths + high clustering; the baseline
  intuition for why a localized outbreak reaches the whole network fast.
- **Barabási & Albert (1999), *Science* — scale-free networks.**
  `barabasi:scaling`. Preferential attachment → power-law degree
  distribution and hubs. Airports are a textbook example.
- **Milo et al. (2002), *Science* — network motifs.**
  `milo:motifs`. Recurrent small subgraphs as "building blocks." Direct
  basis for our subgraph-aware layer.
- **Pržulj (2007), *Bioinformatics* — graphlet degree distribution.**
  `przulj:graphlets`. 73 orbits over 2–5 node graphlets; a fine-grained
  local-structure fingerprint. Borrowed from bio-networks into epi here.

## 2. Compartmental + network epidemiology (the core theory)

- **Kermack & McKendrick (1927) — the original SIR.** `kermack:sir`.
  The compartmental foundation all four of our models extend.
- **Pastor-Satorras & Vespignani (2001), *PRL* — epidemics on scale-free
  nets.** `pastorsatorras:scalefree`. **Key result:** vanishing epidemic
  threshold on scale-free networks → even weak pathogens persist. Explains
  why hubs dominate and why random control fails.
- **Newman (2002), *PRE* — epidemic disease on networks.**
  `newman:spread`. SIR ↔ bond percolation; exact outbreak-size and
  threshold results. The rigorous backbone for "vaccination = site
  percolation."
- **Pastor-Satorras & Vespignani (2002), *PRE* — immunization of complex
  networks.** `pastorsatorras:immunization`. Targeted (hub) immunization
  ≫ random. The theoretical justification for our degree/betweenness arms.
- **Cohen, Havlin & ben-Avraham (2003), *PRL* — acquaintance
  immunization.** `cohen:immunization`. Near-targeted performance using
  only local information. A natural fourth strategy to add.
- **Keeling & Eames (2005), *J. R. Soc. Interface* — networks and epidemic
  models.** `keeling:networks`. Accessible review bridging epidemiology
  and network structure.
- **Pastor-Satorras, Castellano, Van Mieghem & Vespignani (2015), *RMP* —
  epidemic processes in complex networks.** `pastorsatorras:review`. The
  definitive survey; cite for any general claim.
- **Morone & Makse (2015), *Nature* — influence maximization through optimal
  percolation.** `morone:influence`. Collective Influence: the optimal-percolation
  target rule that rewards low-degree, high-impact nodes — implemented as our
  `collective_influence` strategy (item 2), aimed squarely at the anomalous
  gateways degree/betweenness miss.
- **Osat, Faqeeh & Radicchi (2017), *Nat. Commun.* — optimal percolation on
  multiplex networks.** `osat:multiplex`. The multilayer variant of the above; the
  right formulation for our air/land/water multiplex substrate.
- **Radicchi & Castellano (2016), *PRE* — percolation theory to single out
  influential spreaders.** `radicchi:nonbacktracking`. Non-backtracking (Hashimoto)
  spreader ranking; backs our `nonbacktracking` strategy and the non-backtracking
  eigenvalue `lambda_NB` reported (with `T_c = 1/lambda_NB`) in the structure table.

## 2b. Running SIR/SEIR *on* a transport network — the metapopulation framework

> **Directly answers "do we know how SIR works with these networks?" — yes.**
> The standard answer is the **metapopulation reaction–diffusion model**:
> a full compartmental model (SIR/SIS/SEIR/SEIRS/SEIQRD) runs *inside* each node
> (city/region/port), and individuals *diffuse* along the network edges
> between time steps. **This is exactly our blueprint's two-part loop
> (local city dynamics + flight migration).** So our simulator already *is*
> a metapopulation reaction-diffusion model — these papers give it its name
> and its theory, and they generalise unchanged to rail/sea/road layers.

- **Colizza, Pastor-Satorras & Vespignani (2007), *Nature Physics* —
  reaction–diffusion metapopulation models on heterogeneous networks.**
  `colizza:reactiondiffusion`. The foundational "compartmental model inside
  each node + diffusion on edges" formalism. Cite this for *why* our
  local-dynamics-plus-migration loop is principled.
- **Colizza & Vespignani (2007), *PRL* — invasion threshold.**
  `colizza:invasion`. Adds a *global invasion threshold*: below a critical
  mobility rate the disease stays local even if it is locally
  super-critical. Directly relevant to our travel-rate parameter and to
  travel-restriction questions. Works for any layer (air/rail/sea).
- **Mari et al. (2012), *J. R. Soc. Interface* — networked cholera.**
  `mari:cholera`. A concrete compartmental (SIR + Water compartment) model
  run on a **waterway + human-mobility** network. The cleanest example of
  an *actual disease* modelled with compartmental dynamics on a
  water/transport substrate — the template if we add a sea/water layer.
- *(Verify authors)* Area-based **SEIR with a public rail network**
  (Singapore COVID-19, PMC9110328) and **multi-city aviation+railway**
  metapopulation models (India, medRxiv 2020.03.13) show the same
  framework applied to rail specifically.

**Takeaway for the project:** SIR/SEIR/SEIRS/SEIQRD transfer to ground, rail and
sea networks with *no change to the dynamics* — only the edge set and the
per-layer migration rate change. The metapopulation reaction-diffusion
literature is the citable backing for that claim.

## 3. Air-transport / mobility substrate (most relevant)

- **Guimerà, Mossa, Turtschi & Amaral (2005), *PNAS* — worldwide air
  transportation network.** `guimera:anomalous`.
  **Pivotal for our novelty.** The global air network shows *anomalous
  centrality*: due to multi-community structure and geopolitical
  constraints, some **low-degree** airports have **very high betweenness**
  (e.g. Anchorage). ⇒ degree and betweenness can disagree.
- **Colizza, Barrat, Barthélemy & Vespignani (2006), *PNAS* — airline
  network and global epidemics.** `colizza:airline`. The air network
  governs global spread and its predictability. The canonical "why model
  on flights" citation.
- **Balcan et al. (2009), *PNAS* — multiscale mobility networks.**
  `balcan:multiscale`. Couples air travel with short-range commuting in a
  metapopulation model (GLEAM lineage). Future direction if we add ground
  transport.
- **Sun, Hu & Zhu (2023), *Eur. Phys. J. Plus* — centrality anomalies in the
  US domestic air network.** `sun:anomalous`. **The correlated pole of our
  contrast** (replaces the unverifiable "Tanaka 2014" placeholder, which on
  checking turned out to be an economic-geography paper, not a centrality one).
  Builds a false-discovery-rate benchmark and finds betweenness anomalies in
  the US domestic network are **not statistically significant** over 1995–2020
  — and vanish once link weights are used — i.e. big hubs *are* the bridges, so
  degree ≈ betweenness and the two immunisation strategies coincide. Explicitly
  contrasts this with the *worldwide* network's pronounced anomalies (Guimerà).
  ⇒ the US end of the US-like ↔ worldwide-like spectrum, with a published
  anomaly-significance method we mirror in `metrics.anomalous_gateways`.

## 3b. Multimodal: ground, rail & sea layers

For extending beyond air to a multilayer substrate (see the user's
boat/ground question). These are **real, citable** anchors per modality.

- **Balcan et al. (2009), *PNAS*.** `balcan:multiscale`. Couples
  long-range **air** with short-range **commuting**; shows commuting flows
  are ~10× larger than air traffic yet air still sets the global pattern.
  The template for multimodal coupling.
- **Tizzoni et al. (2014), *PLOS Comput. Biol.* — mobility proxies.**
  `tizzoni:proxies`. Compares census commuting, mobile-phone data and
  gravity/radiation models as the **ground-mobility** layer; the choice
  changes predictions. Read before picking a commuting source.
- **Kaluza, Kölzsch, Gastner & Blasius (2010), *J. R. Soc. Interface* —
  global cargo ship network.** `kaluza:cargo`. The canonical **maritime**
  network paper; structure, communities and motifs of global shipping.
- **Seebens, Gastner & Blasius (2013), *Ecology Letters* — bioinvasion via
  shipping.** `seebens:bioinvasion`. Shipping as a disease/invasive-vector
  network (cholera, ballast water). Use to justify a **sea** layer, with
  the caveat that it is cargo/vector-borne, not direct human spread.
- **Rail / high-speed-rail ↔ COVID-19 spread.** ⚠ **Verify authors.**
  Several 2021–2022 studies link HSR connectivity to cross-region
  COVID-19 spread (e.g. "High-Speed railways and the spread of Covid-19",
  PMC9359484; "Beyond the Coronavirus in Wuhan: multi-layer transportation
  network", arXiv:2002.12280). Good support for a **rail** layer — confirm
  the exact citation before adding to the `.bib`.

- **Soriano-Paños, Lotero, Arenas & Gómez (2018), *Phys. Rev. X* —
  multiplex metapopulations.** `sorianopanos:multiplex`. The *more general*
  formalism: the population at each node is partitioned by mobility class, each
  class confined to its own layer, and the threshold depends non-trivially on
  the per-layer patterns. **We do NOT implement this strict form** (it needs
  per-class fractions we cannot calibrate). We implement the **aggregated
  multilayer** metapopulation — one population pool per city, mobility summed
  over layers with per-layer travel rates — which is the standard GLEAM/Balcan
  treatment (`balcan:gleam`, `balcan:multiscale`, `colizza:reactiondiffusion`).
  The strict multiplex is a future refinement, not a claim of this work.

- **Balcan & Vespignani (2011), *Nature Physics* — recurrent mobility.**
  `balcan:recurrent`. **Why our land layer is not diffusion.** Commuting is
  *recurrent* (go to work, return home), not diffusive (permanent relocation),
  and the two give *different invasion thresholds* in principle. So air/water are
  modelled as diffusion (relocation) but **land as recurrent commuting** that
  couples the force of infection between cities without moving residents. We adopt
  recurrent coupling on modelling grounds (commuters return home), not because it
  swings the headline number: at our operating point the two mechanisms give very
  similar European air+land peaks (about 71M recurrent vs 73M diffusive), because
  the air layer already synchronises the continent (see
  [`METHODOLOGY.md`](METHODOLOGY.md) §1 for the verification). An earlier version
  of this note claimed a ~5x reduction (~277M→~49M); that figure does not
  reproduce and is impossible for SIR (peak prevalence cannot exceed ~26%), so it
  has been retracted.

**How flows become coupling (so we don't invent it).** In the metapopulation
framework the migration term is the *per-capita* mobility flux: the fraction
of a city's residents moving to each neighbour per day. So:
- **Land** uses the radiation-model **kernel** `K_ij = flux_ij / pop_i`
  (`simini:radiation`) — a per-capita commuting probability — times a land
  travel rate (a commuting fraction); validated against Eurostat within Europe.
- **Air / water** use route/ferry **frequency** as a passenger-volume proxy
  (no passenger counts in OpenFlights/OSM), each times its own travel rate.
There is **no arbitrary rescaling between layers** — the per-layer travel
rates carry the relative intensities (commuting flux ≫ air, per
`balcan:multiscale`), which is the documentable, citable choice.

**Modelling lesson from the multilayer literature:** coupling layers can
push the system *over* the epidemic threshold even when no single layer
would sustain an outbreak alone. So a multimodal model is not just "more
data" — it can change the qualitative result. Keep layers tagged with
their own travel rates (do not merge).

## 4. Influential spreaders & core structure

- **Kitsak et al. (2010), *Nature Physics* — influential spreaders.**
  `kitsak:spreaders`. **Key result:** the best spreaders sit in the
  network *core* (k-shell), not necessarily the highest-degree or
  highest-betweenness nodes. Justifies our k-core targeting arm.

## 5. Temporal & modern / learning-based

- **Holme & Saramäki (2012), *Physics Reports* — temporal networks.**
  `holme:temporal`. If we ever use time-stamped flight schedules instead
  of a static graph.
- **Liu et al. (2024), *arXiv:2403.19852* — GNNs in epidemic modeling
  (review).** `liu:gnnreview`. Survey of graph-learning approaches; an
  optional, clearly-future extension, not a core claim.

## 6. Tooling

- **Hagberg, Schult & Swart (2008), *SciPy* — NetworkX.**
  `hagberg:networkx`.
- **Di Tommaso et al. (2017), *Nat. Biotechnol.* — Nextflow.**
  `ditommaso:nextflow`. Reproducible workflow engine for our sweeps.
- **OpenFlights — route/airport data.** `openflights`. The substrate.

---

## Where we fit (the novelty argument)

Epidemics-on-flight-networks is **not novel** on its own; the topic runs
from the early 2000s (Colizza, Guimerà) to today. Our defensible,
testable angle:

1. **Europe-specific, five-disease-type comparison** (SIR, SIS, SEIR, SEIRS,
   SEIQRD) under one protocol — a gap in the literature (most work is worldwide
   or US).
2. **The degree–betweenness question for Europe.** There are two regimes
   in the literature:
   - *US-like / correlated* (Sun, Hu & Zhu 2023): hubs are also bridges ⇒
     degree ≈ betweenness ⇒ the two immunisation strategies coincide.
   - *Worldwide-like / anomalous* (Guimerà 2005): community + geopolitical
     structure creates low-degree, high-betweenness gateways ⇒ the
     strategies **diverge**.

   **Our empirical question:** where does Europe sit? Measure
   Spearman ρ(degree, betweenness), find any anomalous gateways, and show
   whether the two strategies' infection curves coincide or separate.
   This is the sharp core of the paper and is genuinely unanswered.
3. **Subgraph/core-aware layer** (k-core, motifs, graphlets) to *target*
   and to *explain* model–strategy outcomes — connecting the result to
   the local structure that causes it.

See [`tex/main.tex`](tex/main.tex) § "Novelty and Positioning" for the
write-up.

## Verified source links

- Pastor-Satorras & Vespignani 2001 — <https://doi.org/10.1103/PhysRevLett.86.3200>
- Newman 2002 — <https://doi.org/10.1103/PhysRevE.66.016128>
- Pastor-Satorras & Vespignani 2002 (immunization) — <https://doi.org/10.1103/PhysRevE.65.036104>
- Cohen, Havlin & ben-Avraham 2003 — <https://doi.org/10.1103/PhysRevLett.91.247901>
- Guimerà et al. 2005 — <https://doi.org/10.1073/pnas.0407994102>
- Colizza et al. 2006 — <https://doi.org/10.1073/pnas.0510525103>
- Balcan et al. 2009 — <https://doi.org/10.1073/pnas.0906910106>
- Kitsak et al. 2010 — <https://doi.org/10.1038/nphys1746>
- Pastor-Satorras et al. 2015 (review) — <https://doi.org/10.1103/RevModPhys.87.925>
- Holme & Saramäki 2012 — <https://doi.org/10.1016/j.physrep.2012.03.001>
- Liu et al. 2024 (GNN review) — <https://arxiv.org/abs/2403.19852>
- Milo et al. 2002 — <https://doi.org/10.1126/science.298.5594.824>
- Pržulj 2007 — <https://doi.org/10.1093/bioinformatics/btl301>
- Tizzoni et al. 2014 (mobility proxies) — <https://doi.org/10.1371/journal.pcbi.1003716>
- Kaluza et al. 2010 (cargo ship network) — <https://doi.org/10.1098/rsif.2009.0495>
- Seebens et al. 2013 (shipping bioinvasion) — <https://doi.org/10.1111/ele.12111>
- Colizza, Pastor-Satorras & Vespignani 2007 (reaction–diffusion metapop.) — <https://doi.org/10.1038/nphys560>
- Colizza & Vespignani 2007 (invasion threshold) — <https://doi.org/10.1103/PhysRevLett.99.148701>
- Mari et al. 2012 (networked cholera) — <https://doi.org/10.1098/rsif.2011.0304>
- van den Driessche & Watmough 2002 (R₀ / next-gen matrix) — <https://doi.org/10.1016/S0025-5564(02)00108-6>
- Balcan et al. 2010 (GLEAM model) — <https://doi.org/10.1016/j.jocs.2010.07.002>
- Balcan et al. 2009 (H1N1 likelihood calibration) — <https://doi.org/10.1186/1741-7015-7-45>
- Balcan & Vespignani 2011 (recurrent mobility) — <https://doi.org/10.1038/nphys1944>
- Soriano-Paños et al. 2018 (multiplex metapopulations) — <https://doi.org/10.1103/PhysRevX.8.031039>
- Rocklöv et al. 2020 (Diamond Princess in-transit/onboard) — <https://doi.org/10.1093/jtm/taaa030>
