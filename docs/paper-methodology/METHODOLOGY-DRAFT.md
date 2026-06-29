# Methodology (draft)

> Draft for Google Docs. Figures are placeholders: **[Figure N: title]** followed by an
> italic description of what to draw. Citations are author–year for readability; bib keys
> live in `disease-types.md` and `../tex/references.bib`. Parameter values are
> literature-sourced (see `disease-types.md`).

## 3. Methodology

Our question is which protection strategy best contains an outbreak on the transport network
that connects Europe, and whether the answer depends on the type of disease. Answering it
fairly requires three components built in sequence: a transport network derived from open
data (Section 3.1), a metapopulation epidemic engine that runs on it (Section 3.2), and a set
of disease types and protection strategies evaluated on top (Sections 3.3 and 3.4).
Section 3.5 states the parameterisation and protocol, and Section 3.6 the implementation. A
single principle constrains every component: across any comparison, only the factor under
study varies, while all other inputs are held fixed. The study is therefore comparative
rather than predictive. We do not estimate how many people a real epidemic would infect; we
quantify differences between scenarios (one strategy versus another, one disease type versus
another) under identical conditions, which are far more robust than absolute incidence on a
synthetic-population network.

### 3.1 Building the map

The substrate is a weighted graph $G=(V,E)$ in which nodes $v\in V$ are cities and edges
$(i,j)\in E$ are travel routes carrying weight $w_{ij}$ proportional to traffic. We construct
$G$ with NetworkX from four open sources: air routes from OpenFlights, city populations from
GeoNames, road and rail topology from OpenStreetMap and GRIP, and ferry routes from
OpenStreetMap. Region is a parameter of construction, which is what allows us to hold the
construction *method* fixed while varying only geography.

Because a single air layer misrepresents how an epidemic actually propagates, the same node
set carries up to three layers, air, land, and water, combined into one shared-node multilayer
network (Figure 2). Edge weights are layer-specific and serve as passenger-volume proxies, but
they come from different recipes according to what data exists. Air weights are real route
frequencies from OpenFlights, and water weights are real ferry-route frequencies counted per
city pair from an OpenStreetMap ferry dump. That dump is filtered to passenger-carrying
services (OSM tag `passenger` not equal to `no`) whose endpoints are at least 5 km apart: the
first filter removes freight-only crossings, since the model concerns human movement, and the
distance threshold discards short river and canal crossings while retaining genuine straits
and sea ferries that connect distinct cities. Land has no comparably uniform relatively easy to flow data across
regions, so its weights are instead modelled with a radiation kernel
$K_{ij} = \mathrm{flux}_{ij}/\mathrm{pop}_i$ (Simini et al., 2012) computed from city
populations. The constraint we impose for fairness is not that all layers share one recipe,
but that each layer is built by a single method applied identically to every region
(OpenFlights for air, the same global ferry dump for water, the radiation kernel for land), so
that differences between regions reflect topology rather than the underlying data source;
European commuting data (Eurostat) is reserved for validating the land kernel within Europe,
not for parameterising any region. Node populations $N_i$ are taken from GeoNames where
available, with a degree-based proxy $N_i = P_0 + d(i)\,P_\mathrm{route}$ as a fallback.

**[Figure 1: Pipeline overview]**
*Three-module pipeline (retrieve, network generation, evaluation): the data sources feeding
each module, the artifacts passing between them (raw data, then GraphML networks, then result
tables and figures), and the two entry points (batch and interactive) that share one engine.*
(source: `diagrams/F1-pipeline.drawio`)

**[Figure 2: Multilayer substrate]**
*Three stacked planes (air, land, water) over the same set of cities, with dashed links
coupling each city across layers; each layer labelled with its edge type and mobility
mechanism.*
(source: `diagrams/F2-multilayer-stack.drawio`)

### 3.2 Running an outbreak on the map

Each city runs a compartmental model internally, while individuals move between cities along
the edges of $G$ once per day. This is a metapopulation reaction–diffusion process (Colizza
et al., 2007): a local *reaction* updates the compartments within each city, and a *mobility*
step couples cities through the network. Within city $i$ the force of infection is
$\lambda_i = \beta\, I_i / N_i$, and a daily step applies the reaction to every city and then
the mobility coupling before advancing to the next day.

The mobility step is where the multilayer map earns its keep. Treating all travel as a single
diffusive process is a known source of error (Balcan & Vespignani, 2011), so the engine
implements two mechanisms matched to the layers:

- **Diffusive mobility (air, water).** A fraction of each compartment leaves city $i$ for
  neighbour $j$ each day, proportional to the layer travel rate $\tau_\ell$ and the normalised
  edge weight $w_{ij}$, and mixes into the destination population. This is the standard
  reaction–diffusion coupling and carries a global invasion threshold in mobility rate
  (Colizza & Vespignani, 2008).
- **Recurrent mobility (land, commuting).** Commuters travel to a neighbour by day, mix
  there, and return home at night, so they are not relocated. We model this by coupling the
  force of infection rather than moving population: residents of $i$ experience
  $\pi_i = \sum_j C_{ij}\, I^{*}_j / N^{*}_j$, where $C$ is the per-capita commuting matrix
  (the land kernel with a stay-home diagonal) and $I^{*}_j = \sum_i C_{ij} I_i$,
  $N^{*}_j = \sum_i C_{ij} N_i$ are the infectious and total people present at $j$. When no
  land layer is present $C$ is the identity and $\pi_i = I_i/N_i$, recovering the plain
  diffusive model.

The two mechanisms are distinct in principle: diffusive travel relocates people permanently,
whereas recurrent commuting returns them home each night, so recurrent coupling is the
appropriate model for daily commuting. On the European air+land network (SIR with
$\beta=0.32$, $\gamma=0.12$; air travel rate 0.0002, land commuting rate 0.3; seed size 2500;
210 days; averaged over seeds 0–2) the two mechanisms give very similar peak active infection
(about 71M recurrent versus 73M diffusive), because the air layer already synchronises the
continent; the difference is larger and in the expected direction (diffusion peaks higher and
earlier) only when air is removed or on a controlled chain network, and even then it stays
under about 20%. Both peaks sit just below the analytic ceiling for a fully synchronised SIR
at this reproduction number (about 26% of the population), which is the main check that the
engine behaves sensibly. We therefore adopt the recurrent mechanism on modelling grounds
(commuters return home), not because it dominates the outcome at this operating point.
As a refinement axis (off by default), transmission may also occur in transit, by running the
full reaction on a travelling cohort for the trip duration; this matters most for long ferry
journeys.

**[Figure 3: Reaction–diffusion loop]**
*One city as a box of compartment transitions (e.g. S, E, I, R with rates $\lambda$,
$\sigma$, $\gamma$), flanked by the two mobility mechanisms (diffusive relocation, and
recurrent commute-and-return with the $\pi_i$ coupling), and the daily loop: reaction, then
mobility, then next day.*
(source: `diagrams/F3-reaction-diffusion.drawio`)

### 3.3 Choosing what to spread

The engine runs whichever compartmental model it is given, which makes the choice of diseases
the substantive decision. Rather than commit to named pathogens, whose exact parameters are
endlessly contestable, we test five disease *types*, each defined by its dynamical structure
and parameterised from one representative exemplar using values drawn entirely from the
literature (Table 1). The five types span the qualitative behaviours relevant to the question:
an immunizing acute epidemic (SIR), an infection with a latent period (SEIR), a lethal
infection controllable by isolation (SEIQR with a fatal compartment), an endemic infection
conferring no immunity (SIS), and a recurrent infection with waning immunity (SEIRS). Each
type adds one mechanism relative to the previous, so a difference in outcome is attributable
to that mechanism rather than to several simultaneous changes.

**Table 1: Disease types, models, and parameters.**

| Type | Model | Example diseases | γ | σ | κ | ω | μ | R₀ |
|------|-------|------------------|---|---|---|---|---|----|
| Immunizing, acute | SIR | measles, rubella, mumps | 0.13 | n/a | 0 | 0 | ≈0 | 12–18 |
| Latent + immunizing | SEIR | COVID-19, SARS, chickenpox | 0.13 | 0.20 | 0 | 0 | ~0.01 | 2–3.3 |
| Lethal, isolation-controlled | SEIQR+D | Ebola, Marburg, plague | 0.10 | 0.09 | 0.20 | 0 | 0.71 | 1.5–2.5 |
| Endemic, no immunity | SIS | gonorrhea, chlamydia, cold | ~0.01–0.05 | n/a | 0 | ∞ | 0 | low (≳1) |
| Recurrent, waning immunity | SEIRS | influenza, RSV, norovirus | 0.21 | 0.70 | 0 | ~0.001 | ~0.001 | 1.3–1.8 |

*Rates are per day, obtained as the reciprocal of a clinical duration; every value is sourced
in `disease-types.md`. The transmission rate $\beta$ is not set directly but derived from
$R_0$ (Section 3.5). The infectious period and $R_0$ are independent quantities: the
immunizing and lethal types have comparable infectious periods (about 8 to 10 days) yet
$R_0$ differs roughly sevenfold, because transmissibility $\beta$ differs, not duration.*

### 3.4 Choosing how to defend

With the disease types fixed, the remaining variable is the intervention, and the network
structure of Section 3.1 defines the available choices, because each intervention is a
decision about which structural elements to remove. Under a fixed budget we compare two modes.
The first is node targeting (vaccination): a fixed number of cities are rendered immune so
that they no longer transmit. The targeting rule is the object of study, and we compare no
intervention (control), random selection, selection by degree (the highest-traffic cities),
selection by betweenness (the structural bridges), and a structural rule based on $k$-core and
motif membership rather than raw connectivity (Kitsak et al., 2010). We additionally vary
coverage between low and high adherence. The second mode is edge targeting (interdiction): we
close routes rather than immunise cities, in four scenarios: (A) no intervention; (B) close
all air routes while retaining land and water; (C) close all air routes within an air-only
model; and (D) close only the top-$k$ routes ranked by degree versus by betweenness.
Scenarios B and C exist specifically to contrast the conclusion a single-layer model reaches
with the behaviour of the full multilayer network.

**[Figure 4: Protection strategies (optional)]**
*The two intervention modes on the same small network: node targeting (selected cities made
immune) and edge targeting (selected routes closed).*

### 3.5 Keeping the comparison honest

The clinical rates $\gamma$, $\sigma$, $\kappa$ are fixed from each type's exemplar, and $R_0$
is taken from the epidemiological literature. The transmission rate is then derived rather
than assumed: on a heterogeneous network the well-mixed identity $R_0=\beta/\gamma$ does not
hold, so we use $R_0 \propto (\beta/\gamma)\,\langle k^2\rangle/\langle k\rangle$
(Pastor-Satorras & Vespignani, 2001) to back out $\beta$, and compute $R_0$ for the
multi-compartment models (SEIR, SEIQR) with the next-generation matrix (van den Driessche &
Watmough, 2002). We do not calibrate to outbreak data, because the transport network carries
no ground-truth epidemic to fit; absolute incidence is consequently illustrative. In place of
calibration we take three steps: we select an operating point in the $R_0$ regime where
strategies actually differ (a trivially total or trivially extinct outbreak ranks all
strategies equally); we run a sensitivity sweep confirming that the *ranking* of strategies
is stable under perturbation of $\beta$, the travel rate, coverage, and efficacy; and we
verify the engine against analytic limits, namely single-node dynamics and the final-size
correspondence between SIR and bond percolation (Newman, 2002). Across any comparison the only
inputs that change are the disease type, the protection strategy, the layer set, and the
random seed. Outcomes are reported as final epidemic size, peak active infection, and peak
day, averaged over seeds.

### 3.6 Making it reproducible

The pipeline is structured so that any result is reproducible. The three modules (retrieve,
network generation, evaluation) chain together so that each run is a pure function of its
configuration and random seed, and the full sweep over regions, layer sets, disease types,
strategies, coverages, and seeds is orchestrated with Nextflow (Di Tommaso et al., 2017). The
same engine is exposed through an interactive simulator that runs a chosen scenario day by
day; both the batch and interactive paths emit identical result artifacts, so the simulator
serves reproducibility and inspection rather than constituting a separate experiment.

**[Figure 5: Simulator (optional)]**
*Screenshot of the simulator mid-run: the live epidemic curve and the map of infected
cities.*
