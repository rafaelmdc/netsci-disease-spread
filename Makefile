# netsci-disease-spread — end-to-end pipeline.
#
# THE one command (self-contained: needs only Docker + Nextflow on the host):
#   make            # = make run
#   make run        # build the image, then run the whole pipeline via Nextflow
#
# `make run` builds the project image and runs retrieve -> netgen -> sweep --maps
# -> collect -> structure -> { interdiction, site } with Nextflow's live UI.
# Customise via Nextflow params, e.g.:
#   make run NFARGS="--maps false"                 # skip the heavy outbreak maps
#   make run NFARGS="--config configs/experiment_multimodal.yaml"
#
# Other targets:
#   make app        # launch the interactive explorer (http://127.0.0.1:8050)
#   make bake       # same pipeline WITHOUT Docker, in your active env (conda etc.)
#   make clean      # wipe results/ (keeps downloaded data/)

CONFIG       ?= experiment.yaml
INTERDICTION ?= configs/europe_interdiction.yaml
RESULTS      ?= results
NFARGS       ?=

.PHONY: default run build bake retrieve netgen sweep collect structure interdiction site app nextflow clean cleaner

default: run

## run: THE one command — build the image, then run the whole pipeline (Nextflow + Docker)
run: build
	nextflow run workflow/main.nf -ansi-log true $(NFARGS)
	@echo "✓ pipeline complete — explore it with: make app   (or open $(RESULTS)/index.html)"

## build: build the self-contained project image (no local Python needed)
build:
	docker compose build

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

## app: launch the Dash explorer in the container at http://127.0.0.1:8050
app:
	docker compose run --rm --service-ports app viz app --host 0.0.0.0

## nextflow: same pipeline via Nextflow, local executor, no Docker
nextflow:
	nextflow run workflow/main.nf -profile local $(NFARGS)

## clean: remove results/ (keeps downloaded data/)
clean:
	rm -rf $(RESULTS) && mkdir -p $(RESULTS)
	@echo "✓ results/ cleared"

## cleaner: also clear Nextflow work/ and run reports
cleaner: clean
	rm -rf work .nextflow .nextflow.log* report-*.html dag-*.html
	@echo "✓ nextflow artifacts cleared"
