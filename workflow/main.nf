#!/usr/bin/env nextflow
// Reproducible end-to-end pipeline. Every process runs in the project image
// (see ../nextflow.config), so a cluster run is byte-identical to a laptop run.
//
//   nextflow run workflow/main.nf -with-docker
//
// Stages: retrieve -> netgen build-all -> evaluate sweep -> collect -> compare.
// The sweep parallelises internally; finer per-config fan-out is a future
// refinement (tracked in docs/ROADMAP.md).

nextflow.enable.dsl = 2

params.config = 'experiment.yaml'

process RETRIEVE {
    output: path 'done_retrieve'
    script:
    """
    netsci retrieve openflights
    touch done_retrieve
    """
}

process NETGEN {
    input:  path _ready
    output: path 'done_netgen'
    script:
    """
    netsci netgen build-all --config ${params.config}
    touch done_netgen
    """
}

process SWEEP {
    input:  path _ready
    output: path 'done_sweep'
    script:
    """
    netsci evaluate sweep --config ${params.config}
    touch done_sweep
    """
}

process COLLECT {
    input:  path _ready
    output: path 'done_collect'
    script:
    """
    netsci evaluate collect
    netsci viz compare
    touch done_collect
    """
}

workflow {
    RETRIEVE | NETGEN | SWEEP | COLLECT
}
