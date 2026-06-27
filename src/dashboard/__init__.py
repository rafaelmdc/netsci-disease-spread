"""The simulator web app: a FastAPI dashboard + arq worker.

Design a scenario, launch it, watch the outbreak simulate live (day-by-day over
SSE), then explore the results — all in the browser. A thin control plane: the
worker calls the same `src.evaluate` engine the CLI/Nextflow pipeline uses, so
artifacts land in the usual `results/` tree.
"""
