#!/usr/bin/env nextflow
// Reproducible end-to-end pipeline, in the order the methodology tells it.
//
//   nextflow run workflow/main.nf                     # self-contained Docker run (default)
//   nextflow run workflow/main.nf -profile local      # active conda env, no Docker
//
// The story the stages tell:
//   1. retrieve            open data sources (OpenFlights, GeoNames, OSM ferries)
//   2. netgen build-all    every network the methodology needs (air across regions
//                          + the europe air -> +land -> +water ladder)
//   3. simulate            the epidemic stages (default: the staged protocol --
//                          spread, then vaccinate, then re-check the winner on the
//                          other diseases; see src/evaluate/staged.py). Set
//                          protocol.mode: factorial in the config for the full grid.
//   4. collect/structure   aggregate runs -> tables + the cross-region spectrum
//   5. interdiction        EDGE closures (scenarios A-D) run twice: once across the
//                          AIR substrate, then again across AIR+LAND+WATER
//   6. figures             static paper figures + tables (PDF/SVG/LaTeX) -> docs/tex/
//   7. site                navigable static site (never re-simulates)
//
// Params (override with --name value):
//   --config             experiment grid + networks   (default experiment.yaml)
//   --interdiction_air   air-only interdiction config  (configs/europe_air_interdiction.yaml)
//   --interdiction_multi multimodal interdiction config (configs/europe_interdiction.yaml)
//   --maps               record per-node history for the animated outbreak maps
//                        (default true; ~2 GB / ~50 min. Use `--maps false` to skip.)

nextflow.enable.dsl = 2

params.config             = 'experiment.yaml'
params.interdiction_air   = 'configs/europe_air_interdiction.yaml'
params.interdiction_multi = 'configs/europe_interdiction.yaml'
params.maps               = true

// 1. Open data sources.
process RETRIEVE {
    output: path 'done'
    script:
    """
    netsci retrieve all
    touch done
    """
}

// 2. Build every (region x layer-set) network the methodology names.
process NETGEN {
    input:  path _ready
    output: path 'done'
    script:
    """
    netsci netgen build-all --config ${params.config}
    touch done
    """
}

// 3. The epidemic stages, driven by `protocol.mode` in the config:
//    staged   = spread -> vaccinate -> re-check (the ~140-run coordinate descent;
//               stage 2's results pick which strategy stage 3 verifies);
//    factorial = the full ~864-run grid (swap the command below for `sweep`).
//    `--maps` records per-node history so the explorer draws every run's animated
//    map with no re-simulation. Toggle with --maps.
process SIMULATE {
    input:  path _ready
    output: path 'done'
    script:
    def maps = params.maps ? '--maps' : ''
    """
    netsci evaluate staged --config ${params.config} ${maps}
    touch done
    """
}

// 4. Aggregate runs -> summary tables + cross-region degree-betweenness spectrum.
process COLLECT {
    input:  path _ready
    output: path 'done'
    script:
    """
    netsci evaluate collect
    netsci evaluate structure
    touch done
    """
}

// 5. EDGE closures (scenarios A-D), once per substrate family. `tag` only keeps
//    Nextflow's two instances distinct in the live log.
process INTERDICTION {
    tag "${tag}"
    input:
        path _ready
        tuple val(tag), val(cfg)
    output: path 'done'
    script:
    """
    netsci evaluate interdiction --config ${cfg}
    touch done
    """
}

// 6. Static paper figures + tables (PDF/SVG/LaTeX) into docs/tex/. Depends on
//    interdiction so F7's scenario series exist.
process FIGURES {
    input:  path _interdiction_done
    output: path 'done'
    script:
    """
    netsci viz paper
    touch done
    """
}

// 7. Navigable static site from on-disk runs (never simulates).
process SITE {
    input:  path _ready
    output: path 'done'
    script:
    """
    netsci viz site
    touch done
    """
}

workflow {
    // Every upstream process runs once (no queue inputs), so `ready` is a value
    // channel: it fans out to BOTH interdiction substrates instead of being
    // consumed after the first.
    ready = COLLECT(SIMULATE(NETGEN(RETRIEVE())))
    // Interdiction across AIR, then the same across AIR+LAND+WATER.
    substrates = Channel.of(
        ['air',        params.interdiction_air],
        ['multimodal', params.interdiction_multi],
    )
    interdicted = INTERDICTION(ready, substrates)
    // Paper figures wait for BOTH interdiction substrates (F7 needs both series).
    FIGURES(interdicted.collect())
    SITE(ready)
}
