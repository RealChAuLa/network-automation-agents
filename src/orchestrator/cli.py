"""
Orchestrator CLI

Command-line interface for the orchestrator.
"""

import asyncio
import signal
import json
from datetime import datetime
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout

from src.orchestrator.orchestrator import Orchestrator
from src.orchestrator.models import PipelineConfig, PipelineStatus

console = Console()

# Global orchestrator instance
_orchestrator: Optional[Orchestrator] = None
_shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global _shutdown_requested
    console.print("\n[yellow]Shutdown requested.. .[/yellow]")
    _shutdown_requested = True
    if _orchestrator:
        asyncio.create_task(_orchestrator.stop())


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Orchestrator CLI

    Coordinate all agents and run the automation pipeline.
    """
    pass


@cli.command()
@click.option("--interval", "-i", default=5, help="Minutes between runs")
@click.option("--dry-run", is_flag=True, help="Simulate execution")
@click.option("--no-llm", is_flag=True, help="Skip LLM analysis")
@click.option("--no-verify", is_flag=True, help="Skip post-execution verification")
def start(interval: int, dry_run: bool, no_llm: bool, no_verify: bool):
    """Start the orchestrator (runs continuously)."""
    global _orchestrator, _shutdown_requested

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    config = PipelineConfig(
        use_llm=not no_llm,
        verify_execution=not no_verify,
        dry_run=dry_run,
    )

    console.print(Panel(
        f"[bold]Orchestrator Starting[/bold]\n\n"
        f"Interval: {interval} minutes\n"
        f"Dry Run: {'Yes' if dry_run else 'No'}\n"
        f"LLM: {'Disabled' if no_llm else 'Enabled'}\n"
        f"Verification: {'Disabled' if no_verify else 'Enabled'}\n\n"
        f"Press Ctrl+C to stop",
        title="Network Automation Orchestrator",
        border_style="green"
    ))

    async def _start():
        global _orchestrator
        _orchestrator = Orchestrator(
            interval_minutes=interval,
            config=config,
        )
        await _orchestrator.start()

    asyncio.run(_start())

    console.print("\n[green]✓ Orchestrator stopped gracefully[/green]")


@cli.command()
@click.option("--dry-run", is_flag=True, help="Simulate execution")
@click.option("--no-llm", is_flag=True, help="Skip LLM analysis")
@click.option("--no-verify", is_flag=True, help="Skip verification")
@click.option("--skip-execution", is_flag=True, help="Skip execution step")
@click.option("--output", "-o", type=click.Path(), help="Save result to JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def run(dry_run: bool, no_llm: bool, no_verify: bool, skip_execution: bool,
        output: Optional[str], verbose: bool):
    """Run the pipeline once (single run, then exit)."""

    config = PipelineConfig(
        use_llm=not no_llm,
        verify_execution=not no_verify,
        dry_run=dry_run,
        skip_execution=skip_execution,
    )

    console.print(Panel(
        f"[bold]Single Pipeline Run[/bold]\n\n"
        f"Dry Run: {'Yes' if dry_run else 'No'}\n"
        f"LLM:  {'Disabled' if no_llm else 'Enabled'}\n"
        f"Skip Execution: {'Yes' if skip_execution else 'No'}",
        title="Pipeline",
        border_style="blue"
    ))

    async def _run():
        orchestrator = Orchestrator(config=config)
        result = await orchestrator.run_now(config=config, trigger="manual")
        return result

    result = asyncio.run(_run())

    _display_run_result(result, verbose)

    if output:
        with open(output, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        console.print(f"\n[green]✓ Result saved to {output}[/green]")


@cli.command()
def status():
    """Show orchestrator status (for running instance)."""

    # Since we can't easily get status of a running orchestrator from CLI,
    # we'll show configuration and last known state
    console.print(Panel(
        "[bold]Orchestrator Configuration[/bold]\n\n"
        "To see live status, run the orchestrator with:\n"
        "  python -m src. orchestrator.cli start\n\n"
        "For a single run with status:\n"
        "  python -m src.orchestrator. cli run --verbose",
        title="Status",
        border_style="cyan"
    ))


@cli.command()
@click.option("--limit", "-l", default=10, help="Number of runs to show")
def history(limit: int):
    """Show recent run history."""

    async def _history():
        orchestrator = Orchestrator()
        runs = orchestrator.get_run_history(limit=limit)
        return runs

    runs = asyncio.run(_history())

    if not runs:
        console.print("[yellow]No run history available[/yellow]")
        console.print("Run the pipeline first with:  python -m src. orchestrator.cli run")
        return

    table = Table(title=f"Recent Pipeline Runs ({len(runs)})")
    table.add_column("ID", style="cyan")
    table.add_column("Status")
    table.add_column("Issues", style="yellow")
    table.add_column("Actions", style="green")
    table.add_column("Duration", style="dim")
    table.add_column("Time", style="dim")

    for run in runs:
        status_display = {
            PipelineStatus.SUCCESS: "[green]✓ SUCCESS[/green]",
            PipelineStatus.PARTIAL: "[yellow]⚠ PARTIAL[/yellow]",
            PipelineStatus.FAILED: "[red]✗ FAILED[/red]",
            PipelineStatus.CANCELLED: "[dim]CANCELLED[/dim]",
            PipelineStatus.SKIPPED: "[dim]SKIPPED[/dim]",
        }.get(run.status, run.status.value)

        table.add_row(
            run.id[-12:],
            status_display,
            str(run.issues_found),
            f"{run.actions_successful}/{run.actions_executed}",
            f"{run.duration_ms}ms" if run.duration_ms else "-",
            run.started_at.strftime("%Y-%m-%d %H:%M") if run.started_at else "-",
        )

    console.print(table)


@cli.command()
def config():
    """Show default pipeline configuration."""

    cfg = PipelineConfig.from_env()

    console.print(Panel(
        f"[bold]Pipeline Configuration[/bold]\n\n"
        f"[bold]Agent Settings:[/bold]\n"
        f"  Use LLM: {cfg.use_llm}\n"
        f"  Verify Execution: {cfg.verify_execution}\n"
        f"  Dry Run: {cfg.dry_run}\n\n"
        f"[bold]Step Control:[/bold]\n"
        f"  Skip Discovery: {cfg.skip_discovery}\n"
        f"  Skip Policy: {cfg.skip_policy}\n"
        f"  Skip Compliance: {cfg.skip_compliance}\n"
        f"  Skip Execution: {cfg.skip_execution}\n\n"
        f"[bold]Behavior:[/bold]\n"
        f"  Stop on No Issues: {cfg.stop_on_no_issues}\n"
        f"  Stop on No Actions: {cfg.stop_on_no_actions}\n"
        f"  Max Actions Per Run: {cfg.max_actions_per_run}",
        title="Configuration",
        border_style="cyan"
    ))


@cli.command()
def graph():
    """Show the LangGraph pipeline visualization."""

    from src.orchestrator.pipeline import Pipeline

    pipeline = Pipeline()

    console.print(Panel(
        pipeline.get_graph_visualization(),
        title="LangGraph Pipeline",
        border_style="cyan"
    ))


def _display_run_result(run, verbose: bool = False):
    """Display a pipeline run result."""

    status_display = {
        PipelineStatus.SUCCESS: ("✅", "green"),
        PipelineStatus.PARTIAL: ("⚠️", "yellow"),
        PipelineStatus.FAILED: ("❌", "red"),
        PipelineStatus.CANCELLED: ("🚫", "dim"),
        PipelineStatus.SKIPPED: ("⏭️", "dim"),
    }

    emoji, color = status_display.get(run.status, ("❓", "white"))

    # Summary panel
    console.print(Panel(
        f"{emoji} [bold]Status: [{color}]{run.status.value.upper()}[/{color}][/bold]\n\n"
        f"Run ID: {run.id}\n"
        f"Duration: {run.duration_ms}ms\n"
        f"Trigger: {run.trigger}\n\n"
        f"[bold]Pipeline Results:[/bold]\n"
        f"  Issues Found: {run.issues_found}\n"
        f"  Actions Recommended: {run.actions_recommended}\n"
        f"  Actions Approved: {run.actions_approved}\n"
        f"  Actions Executed: {run.actions_executed}\n"
        f"  Actions Successful: {run.actions_successful}",
        title="Pipeline Run Result",
        border_style=color
    ))

    if run.summary:
        console.print(f"\n[bold]Summary:[/bold] {run.summary}")

    # Steps table
    if run.steps:
        table = Table(title="Pipeline Steps")
        table.add_column("Step", style="cyan")
        table.add_column("Status")
        table.add_column("Items", style="green")
        table.add_column("Duration", style="dim")

        for step_name, step in run.steps.items():
            step_status = {
                "success": "[green]✓ SUCCESS[/green]",
                "failed": "[red]✗ FAILED[/red]",
                "skipped": "[dim]SKIPPED[/dim]",
                "running": "[blue]RUNNING[/blue]",
                "pending": "[dim]PENDING[/dim]",
            }.get(step.status.value, step.status.value)

            items = f"{step.items_passed}/{step.items_processed}"
            if step.items_failed > 0:
                items += f" ([red]{step.items_failed} failed[/red])"

            table.add_row(
                step_name.title(),
                step_status,
                items,
                f"{step.duration_ms}ms" if step.duration_ms else "-",
            )

        console.print(table)

    # Show errors if verbose
    if verbose:
        for step_name, step in run.steps.items():
            if step.error:
                console.print(f"\n[red]Error in {step_name}:[/red] {step.error}")


if __name__ == "__main__":
    cli()