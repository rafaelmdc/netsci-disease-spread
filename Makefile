# netsci-disease-spread — end-to-end pipeline.
#
# Runs `netsci` directly in your active environment (the conda `datascience`
# env, where the CLI and downloaded data already live). No container needed.
# For a containerised / DAG-tracked run instead, see `make nextflow`.
#
# Usage:
#   make            # = make bake  (the full run, with per-node outbreak maps)
#   make bake       # retrieve? -> netgen -> sweep --maps -> collect -> structure -> interdiction -> site
#   make sweep      # just the 864-run grid WITH maps (re-runs everything downstream too)
#   make app        # launch the interactive explorer
#   make clean      # wipe results/ (keeps downloaded data/)

CONFIG       ?= experiment.yaml
INTERDICTION ?= configs/europe_interdiction.yaml
RESULTS      ?= results

.PHONY: default bake retrieve netgen sweep collect structure interdiction site app nextflow clean cleaner

default: bake

## bake: full reproducible pipeline -> tables, maps, interdiction, navigable site
bake: site interdiction
	@echo "✓ bake complete — browse with: make app   (or open $(RESULTS)/index.html)"

## retrieve: one-time source downloads (OpenFlights, GeoNames, OSM ferries)
retrieve:
	netsci retrieve all

## netgen: build every (region x layer-set) network named in $(CONFIG)
netgen:
	netsci netgen build-all --config $(CONFIG)

## sweep: run the whole grid AND record per-node history for the outbreak maps
sweep:
	netsci evaluate sweep --config $(CONFIG) --maps

## collect: aggregate run JSONs -> summary.parquet + strategy_gap.parquet
collect: sweep
	netsci evaluate collect

## structure: cross-region degree-betweenness spectrum -> structure.parquet
structure: collect
	netsci evaluate structure

## interdiction: scenarios A-D on the flagship multilayer network
interdiction: structure
	netsci evaluate interdiction --config $(INTERDICTION)

## site: (re)build the navigable static site from on-disk runs (never simulates)
site: structure
	netsci viz site

## app: launch the Dash explorer (rebuilds tables on launch if missing)
app:
	netsci viz app

## nextflow: same pipeline via Nextflow, local executor, no Docker
nextflow:
	nextflow run workflow/main.nf -profile local

## clean: remove results/ (keeps downloaded data/)
clean:
	rm -rf $(RESULTS) && mkdir -p $(RESULTS)
	@echo "✓ results/ cleared"

## cleaner: also clear Nextflow work/ and run reports
cleaner: clean
	rm -rf work .nextflow .nextflow.log* report-*.html dag-*.html
	@echo "✓ nextflow artifacts cleared"
