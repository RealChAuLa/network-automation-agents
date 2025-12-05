"""
Discovery Agent CLI Runner

Provides command-line interface and scheduled running for the Discovery Agent.
"""

import asyncio
import json
import time
import signal
import sys
import threading
from datetime import datetime
from typing import Optional

import click
import schedule
from rich.console import Console
from rich. table import Table
from rich.panel import Panel

from src.agents.discovery.agent import DiscoveryAgent
from src.agents.discovery.models import IssueSeverity
from src.agents.config import config

console = Console()

# Global flag for graceful shutdown
_shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global _shutdown_requested
    console.print("\n[yellow]Shutdown requested.. .[/yellow]")
    _shutdown_requested = True


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Discovery Agent CLI

    Monitor the network and detect anomalies.
    """
    pass


@cli.command()
@click.option("--node", "-n", default=None, help="Specific node ID to analyze")
@click.option("--no-logs", is_flag=True, help="Skip log analysis")
@click.option("--no-llm", is_flag=True, help="Skip LLM analysis (rule-based only)")
@click.option("--output", "-o", type=click.Path(), help="Save report to JSON file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def run(node: Optional[str], no_logs: bool, no_llm: bool, output: Optional[str], verbose: bool):
    """Run a single discovery diagnosis."""

    async def _run():
        console.print(Panel(
            f"[bold]Discovery Agent[/bold]\n"
            f"Scope: {node or 'network-wide'}\n"
            f"Logs: {'disabled' if no_logs else 'enabled'}\n"
            f"LLM: {'disabled' if no_llm else 'enabled if configured'}",
            title="Starting Diagnosis",
            border_style="blue"
        ))

        agent = DiscoveryAgent()

        # Show LLM status
        if agent.llm_available:
            console.print(f"[green]✓ LLM available: {agent.llm. provider_name} ({agent.llm.model})[/green]")
        else:
            console.print("[yellow]⚠ LLM not available, using rule-based analysis[/yellow]")

        console.print("\n[bold]Running diagnosis...[/bold]\n")

        result = await agent.run(
            node_id=node,
            include_logs=not no_logs,
            use_llm=not no_llm if not no_llm else False,
        )

        if result.success:
            report = result.result
            _display_report(report, verbose)

            # Save to file if requested
            if output:
                with open(output, "w") as f:
                    json.dump(report. to_dict(), f, indent=2)
                console.print(f"\n[green]✓ Report saved to {output}[/green]")
        else:
            console.print(f"[red]✗ Diagnosis failed: {result.error}[/red]")

    asyncio.run(_run())


@cli.command()
@click. option("--interval", "-i", default=None, type=int, help="Interval in minutes (default: from config)")
@click.option("--no-llm", is_flag=True, help="Skip LLM analysis")
def watch(interval: Optional[int], no_llm: bool):
    """Run continuous monitoring on a schedule."""
    global _shutdown_requested

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    interval_minutes = interval or config.discovery. interval_minutes

    console.print(Panel(
        f"[bold]Discovery Agent - Watch Mode[/bold]\n"
        f"Interval: {interval_minutes} minutes\n"
        f"LLM: {'disabled' if no_llm else 'enabled if configured'}\n\n"
        f"Press Ctrl+C to stop",
        title="Starting Continuous Monitoring",
        border_style="blue"
    ))

    # Create agent once and reuse it
    agent = DiscoveryAgent()

    if agent.llm_available:
        console.print(f"[green]✓ LLM available: {agent.llm.provider_name}[/green]")
    else:
        console.print("[yellow]⚠ LLM not available, using rule-based analysis[/yellow]")

    run_count = 0

    # Create a single event loop for the entire watch session
    loop = asyncio. new_event_loop()
    asyncio.set_event_loop(loop)

    async def run_diagnosis_async():
        """Run diagnosis asynchronously."""
        nonlocal run_count
        run_count += 1

        console.print(f"\n[dim]{'─' * 60}[/dim]")
        console.print(f"[bold]Run #{run_count}[/bold] - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            result = await agent.run(use_llm=not no_llm if not no_llm else False)

            if result.success:
                report = result.result
                _display_report_summary(report)
            else:
                console.print(f"[red]✗ Error: {result.error}[/red]")
        except Exception as e:
            console. print(f"[red]✗ Exception: {e}[/red]")

    def run_diagnosis_sync():
        """Synchronous wrapper that uses the existing event loop."""
        if not _shutdown_requested:
            try:
                loop.run_until_complete(run_diagnosis_async())
            except Exception as e:
                console. print(f"[red]✗ Error in diagnosis: {e}[/red]")

    try:
        # Run immediately
        run_diagnosis_sync()

        # Schedule future runs
        schedule.every(interval_minutes).minutes.do(run_diagnosis_sync)

        # Main loop
        while not _shutdown_requested:
            schedule.run_pending()
            time.sleep(1)

    finally:
        # Clean up the event loop
        try:
            # Cancel any pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()

            # Run until all tasks are cancelled
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

            loop.close()
        except Exception:
            pass

        console.print("\n[green]✓ Monitoring stopped[/green]")


@cli.command()
@click. option("--interval", "-i", default=None, type=int, help="Interval in minutes (default: from config)")
@click. option("--no-llm", is_flag=True, help="Skip LLM analysis")
def watch_simple(interval: Optional[int], no_llm: bool):
    """Run continuous monitoring (simpler version without LLM between runs)."""
    global _shutdown_requested

    # Set up signal handlers
    signal.signal(signal. SIGINT, signal_handler)
    signal.signal(signal. SIGTERM, signal_handler)

    interval_minutes = interval or config.discovery.interval_minutes

    console.print(Panel(
        f"[bold]Discovery Agent - Watch Mode (Simple)[/bold]\n"
        f"Interval: {interval_minutes} minutes\n"
        f"LLM: {'disabled' if no_llm else 'enabled if configured'}\n\n"
        f"Press Ctrl+C to stop",
        title="Starting Continuous Monitoring",
        border_style="blue"
    ))

    run_count = 0

    def run_single_diagnosis():
        """Run a single diagnosis with fresh agent."""
        nonlocal run_count

        if _shutdown_requested:
            return

        run_count += 1

        console.print(f"\n[dim]{'─' * 60}[/dim]")
        console.print(f"[bold]Run #{run_count}[/bold] - {datetime. now().strftime('%Y-%m-%d %H:%M:%S')}")

        async def _diagnosis():
            # Create fresh agent for each run to avoid event loop issues
            agent = DiscoveryAgent()
            result = await agent.run(use_llm=not no_llm if not no_llm else False)

            if result. success:
                _display_report_summary(result.result)
            else:
                console.print(f"[red]✗ Error: {result.error}[/red]")

        try:
            asyncio.run(_diagnosis())
        except Exception as e:
            console.print(f"[red]✗ Exception: {e}[/red]")

    # Run immediately
    run_single_diagnosis()

    # Schedule future runs
    schedule. every(interval_minutes).minutes. do(run_single_diagnosis)

    # Main loop
    while not _shutdown_requested:
        schedule.run_pending()
        time.sleep(1)

    console.print("\n[green]✓ Monitoring stopped[/green]")


@cli.command()
def status():
    """Show agent status and configuration."""

    async def _status():
        agent = DiscoveryAgent()

        console.print(Panel(
            f"[bold]Discovery Agent Status[/bold]\n\n"
            f"[bold]LLM Configuration:[/bold]\n"
            f"  Provider: {config.llm.provider}\n"
            f"  Available: {'✓ Yes' if agent.llm_available else '✗ No'}\n"
            f"  Model: {agent.llm.model if agent.llm_available else 'N/A'}\n\n"
            f"[bold]Analysis Thresholds:[/bold]\n"
            f"  CPU Warning/Critical: {config.discovery.cpu_warning_threshold}% / {config.discovery.cpu_critical_threshold}%\n"
            f"  Memory Warning/Critical: {config.discovery.memory_warning_threshold}% / {config.discovery.memory_critical_threshold}%\n"
            f"  Packet Loss Warning/Critical: {config.discovery. packet_loss_warning_threshold}% / {config.discovery.packet_loss_critical_threshold}%\n"
            f"  Latency Warning/Critical: {config.discovery.latency_warning_threshold}ms / {config.discovery.latency_critical_threshold}ms\n\n"
            f"[bold]Scheduling:[/bold]\n"
            f"  Enabled: {'✓ Yes' if config. discovery.enabled else '✗ No'}\n"
            f"  Interval: {config. discovery.interval_minutes} minutes",
            title="Agent Status",
            border_style="cyan"
        ))

    asyncio.run(_status())


@cli.command()
def anomalies():
    """Show currently active anomalies."""

    async def _anomalies():
        agent = DiscoveryAgent()
        active = agent.get_active_anomalies()

        if not active:
            console.print("[green]✓ No active anomalies[/green]")
            return

        table = Table(title=f"Active Anomalies ({len(active)})")
        table.add_column("ID", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Severity", style="red")
        table.add_column("Node", style="green")
        table.add_column("Started", style="dim")

        for anomaly in active:
            severity_style = {
                "critical": "red bold",
                "high": "red",
                "medium": "yellow",
                "low": "green",
            }. get(anomaly["severity"], "white")

            table.add_row(
                anomaly["id"],
                anomaly["type"],
                f"[{severity_style}]{anomaly['severity']}[/{severity_style}]",
                anomaly["node_id"],
                anomaly["started_at"][:19],
            )

        console. print(table)

    asyncio.run(_anomalies())


def _display_report(report, verbose: bool = False):
    """Display a full diagnosis report."""
    # Status emoji and color
    status_display = {
        IssueSeverity.CRITICAL: ("🔴", "red bold"),
        IssueSeverity.HIGH: ("🟠", "red"),
        IssueSeverity.MEDIUM: ("🟡", "yellow"),
        IssueSeverity.LOW: ("🟢", "green"),
        IssueSeverity.INFO: ("✅", "green"),
    }

    emoji, color = status_display. get(report.overall_status, ("❓", "white"))

    # Summary panel
    console.print(Panel(
        f"{emoji} [bold]Overall Status: [{color}]{report.overall_status. value. upper()}[/{color}][/bold]\n\n"
        f"Diagnosis ID: {report.id}\n"
        f"Scope: {report.scope}\n"
        f"Nodes Analyzed: {report.nodes_analyzed}\n"
        f"Analysis Method: {report.analysis_method}\n"
        f"Duration: {report.analysis_duration_ms}ms\n\n"
        f"[bold]Issues Found:[/bold] {len(report.issues)}\n"
        f"  • Critical: {report.critical_count}\n"
        f"  • High: {report.high_count}\n"
        f"  • Medium: {report.medium_count}\n"
        f"  • Low: {report. low_count}",
        title="Diagnosis Report",
        border_style=color
    ))

    # Issues table
    if report.issues:
        table = Table(title="Detected Issues")
        table.add_column("#", style="dim")
        table.add_column("Severity", style="bold")
        table.add_column("Type", style="cyan")
        table.add_column("Node", style="green")
        table.add_column("Description")
        table.add_column("Value", style="yellow")

        for i, issue in enumerate(report.issues, 1):
            severity_style = {
                IssueSeverity.CRITICAL: "red bold",
                IssueSeverity.HIGH: "red",
                IssueSeverity.MEDIUM: "yellow",
                IssueSeverity.LOW: "green",
            }.get(issue.severity, "white")

            value_str = ""
            if issue.current_value is not None:
                value_str = f"{issue.current_value}{issue.unit or ''}"

            table. add_row(
                str(i),
                f"[{severity_style}]{issue.severity. value}[/{severity_style}]",
                issue.issue_type. value,
                issue.node_name,
                issue.description[:40] + "..." if len(issue.description) > 40 else issue. description,
                value_str,
            )

        console.print(table)

        # Show detailed issues if verbose
        if verbose:
            for issue in report.issues:
                console.print(f"\n[bold]{issue.issue_type.value}[/bold] on {issue.node_name}")
                console.print(f"  {issue.description}")
                if issue.potential_causes:
                    console.print("  [bold]Potential Causes:[/bold]")
                    for cause in issue.potential_causes[:3]:
                        console.print(f"    • {cause}")
                if issue.recommended_actions:
                    console. print("  [bold]Recommended Actions:[/bold]")
                    for action in issue.recommended_actions[:3]:
                        console.print(f"    • {action}")
                if issue.affected_downstream_nodes:
                    console. print(f"  [bold]Affected Downstream:[/bold] {', '.join(issue.affected_downstream_nodes[:3])}")

    # Root cause analysis
    if report.root_cause_analysis:
        console.print(Panel(
            report.root_cause_analysis,
            title="[bold]Root Cause Analysis (LLM)[/bold]",
            border_style="magenta"
        ))

    # Recommendations
    if report.overall_recommendations:
        console.print("\n[bold]Recommended Actions:[/bold]")
        for i, rec in enumerate(report.overall_recommendations, 1):
            console.print(f"  {i}. {rec}")


def _display_report_summary(report):
    """Display a brief summary of the report."""
    status_display = {
        IssueSeverity.CRITICAL: ("🔴", "red"),
        IssueSeverity. HIGH: ("🟠", "red"),
        IssueSeverity.MEDIUM: ("🟡", "yellow"),
        IssueSeverity.LOW: ("🟢", "green"),
        IssueSeverity.INFO: ("✅", "green"),
    }

    emoji, color = status_display.get(report.overall_status, ("❓", "white"))

    console.print(
        f"{emoji} [{color}]{report.overall_status.value.upper()}[/{color}] | "
        f"Issues: {len(report.issues)} "
        f"(C:{report.critical_count} H:{report.high_count} M:{report.medium_count} L:{report.low_count}) | "
        f"Duration: {report.analysis_duration_ms}ms"
    )

    if report.issues:
        for issue in report.issues[:3]:  # Show top 3 issues
            console.print(f"  • [{issue.severity.value}] {issue.issue_type.value} on {issue.node_name}")

    # Show LLM root cause if available
    if report.root_cause_analysis:
        # Show first 100 chars of root cause
        summary = report.root_cause_analysis[:150]
        if len(report.root_cause_analysis) > 150:
            summary += "..."
        console.print(f"  [magenta]LLM Analysis: {summary}[/magenta]")


if __name__ == "__main__":
    cli()