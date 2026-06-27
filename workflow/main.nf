#!/usr/bin/env nextflow
// Reproducible end-to-end pipeline.
//
//   nextflow run workflow/main.nf                     # self-contained Docker run (default)
//   nextflow run workflow/main.nf -profile local      # active conda env, no Docker
//
// Stages: retrieve -> netgen build-all -> sweep [--maps] -> collect -> structure
//         -> { interdiction, site }.  The sweep parallelises internally; finer
// per-config fan-out is a future refinement (tracked in docs/ROADMAP.md).
//
// Params (override with --name value):
//   --config        experiment grid + networks   (default experiment.yaml)
//   --interdiction  interdiction scenario config  (default configs/europe_interdiction.yaml)
//   --maps          record per-node history for the animated outbreak maps
//                   (default true; ~2 GB / ~50 min. Use `--maps false` to skip.)

nextflow.enable.dsl = 2

params.config       = 'experiment.yaml'
params.interdiction = 'configs/europe_interdiction.yaml'
params.maps         = true

process RETRIEVE {
    output: path 'done'
    script:
    """
    netsci retrieve all
    touch done
    """
}

process NETGEN {
    input:  path _ready
    output: path 'done'
    script:
    """
    netsci netgen build-all --config ${params.config}
    touch done
    """
}

// --maps records per-node history so the explorer draws every run's animated
// map with no re-simulation (~2 GB for the full grid). Toggle with --maps.
process SWEEP {
    input:  path _ready
    output: path 'done'
    script:
    def maps = params.maps ? '--maps' : ''
    """
    netsci evaluate sweep --config ${params.config} ${maps}
    touch done
    """
}

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

// Air-interdiction scenarios A-D on the flagship multilayer network.
process INTERDICTION {
    input:  path _ready
    output: path 'done'
    script:
    """
    netsci evaluate interdiction --config ${params.interdiction}
    touch done
    """
}

// Navigable static site from on-disk runs (never simulates).
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
    ready = COLLECT(SWEEP(NETGEN(RETRIEVE())))
    INTERDICTION(ready)
    SITE(ready)
}
