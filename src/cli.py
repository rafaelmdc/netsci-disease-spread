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


if __name__ == "__main__":
    app()
