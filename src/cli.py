"""Root Typer app: `netsci <module> <command>`.

Mounts the four pipeline modules as sub-apps so the same entrypoint works
on the host (`uv run netsci ...`) and in Docker (`app ...`).
"""

from __future__ import annotations

import typer

from src.evaluate.cli import app as evaluate_app
from src.netgen.cli import app as netgen_app
from src.retrieve.cli import app as retrieve_app
from src.viz.cli import app as viz_app

app = typer.Typer(help="netsci-disease-spread pipeline CLI.", no_args_is_help=True)
app.add_typer(retrieve_app, name="retrieve")
app.add_typer(netgen_app, name="netgen")
app.add_typer(evaluate_app, name="evaluate")
app.add_typer(viz_app, name="viz")


@app.command()
def dashboard(
    host: str = typer.Option("127.0.0.1", help="host to bind"),
    port: int = typer.Option(8000, help="port to serve on"),
    reload: bool = typer.Option(False, help="auto-reload on code changes (dev)"),
) -> None:
    """Launch the simulator web app (FastAPI). Needs Redis and a running worker.

    Requires the `dashboard` extra: `uv sync --extra dashboard`.
    """
    import uvicorn

    typer.echo(f"simulator → http://{host}:{port}  (start the worker too: netsci worker)")
    uvicorn.run("src.dashboard.app:app", host=host, port=port, reload=reload)


@app.command()
def worker() -> None:
    """Run the arq worker that executes queued simulations (needs Redis)."""
    from arq import run_worker

    from src.dashboard.worker import WorkerSettings

    run_worker(WorkerSettings)


if __name__ == "__main__":
    app()
