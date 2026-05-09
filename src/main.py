"""CLI entry point for the research paper agent team."""

import typer

app = typer.Typer(help="Research paper agent team CLI")


@app.command()
def db_init() -> None:
    """Initialize the database."""
    typer.echo("db-init: not implemented (MVP1 placeholder)")


@app.command()
def discover(
    profile: str = typer.Option(..., "--profile", help="Research profile slug"),
    days: int = typer.Option(14, "--days", help="Lookback window in days"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run without writing to DB"),
) -> None:
    """Discover new papers for a research profile."""
    typer.echo(
        f"discover: profile={profile} days={days} dry_run={dry_run} (MVP1 placeholder)"
    )


if __name__ == "__main__":
    app()
