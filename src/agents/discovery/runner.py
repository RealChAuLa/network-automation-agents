"""
Discovery Agent CLI Runner

Command-line interface for the Discovery Agent.
"""

import asyncio
import json
import time
import signal
from datetime import datetime
from typing import Optional

import click
import schedule
from rich. console import Console
from rich.table import Table
from rich.panel import Panel

from src.agents.discovery.agent import DiscoveryAgent
from src. agents.discovery.models import IssueSeverity
from src.agents. config import config

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

    Monitor the network and detect anomalies using MCP tools.
    """
    pass


@cli.command()
@click. option("--node", "-n", default=None, help="Specific node ID to analyze")
@click.option("--no-llm", is_flag=True, help="Skip LLM analysis (MCP tools only)")
@click.option("--output", "-o", type=click.Path(), help="Save report to JSON file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def run(node: Optional[str], no_llm: bool, output: Optional[str], verbose: bool):
    """Run a single discovery diagnosis."""

    async def _run():
        console.print(Panel(
            f"[bold]Discovery Agent (MCP-based)[/bold]\n"
            f"Scope: {node or 'network-wide'}\n"
            f"LLM: {'disabled' if no_llm else 'enabled if configured'}",
            title="Starting Diagnosis",
            border_style="blue"
        ))

        agent = DiscoveryAgent()

        # Show status
        if agent.llm_available:
            console. print(f"[green]✓ LLM available: {agent.llm. provider_name} ({agent.llm. model})[/green]")
        else:
            console.print("[yellow]⚠ LLM not available, using MCP tools directly[/yellow]")

        console.print(f"[cyan]✓ MCP Client ready with {len(agent. mcp_client. get_available_tools())} tools[/cyan]")
        console.print("\n[bold]Running diagnosis...[/bold]\n")

        result = await agent.run(
            node_id=node,
            use_llm=not no_llm,
        )

        if result.success:
            report = result.result
            _display_report(report, verbose)

            if output:
                with open(output, "w") as f:
                    json. dump(report.to_dict(), f, indent=2)
                console.print(f"\n[green]✓ Report saved to {output}[/green]")
        else:
            console.print(f"[red]✗ Diagnosis failed: {result.error}[/red]")

    asyncio.run(_run())


@cli.command()
@click.option("--interval", "-i", default=None, type=int, help="Interval in minutes")
@click.option("--no-llm", is_flag=True, help="Skip LLM analysis")
def watch(interval: Optional[int], no_llm: bool):
    """Run continuous monitoring."""
    global _shutdown_requested

    signal.signal(signal. SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    interval_minutes = interval or config.discovery.interval_minutes

    console.print(Panel(
        f"[bold]Discovery Agent - Watch Mode[/bold]\n"
        f"Interval: {interval_minutes} minutes\n"
        f"LLM: {'disabled' if no_llm else 'enabled if configured'}\n\n"
        f"Press Ctrl+C to stop",
        title="Starting Continuous Monitoring",
        border_style="blue"
    ))

    run_count = 0

    def run_single_diagnosis():
        nonlocal run_count

        if _shutdown_requested:
            return

        run_count += 1
        console.print(f"\n[dim]{'─' * 60}[/dim]")
        console. print(f"[bold]Run #{run_count}[/bold] - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        async def _diagnosis():
            agent = DiscoveryAgent()
            result = await agent.run(use_llm=not no_llm)

            if result.success:
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
    schedule.every(interval_minutes).minutes. do(run_single_diagnosis)

    # Main loop
    while not _shutdown_requested:
        schedule.run_pending()
        time.sleep(1)

    console. print("\n[green]✓ Monitoring stopped[/green]")


@cli.command()
def status():
    """Show agent status."""

    async def _status():
        agent = DiscoveryAgent()

        tools = agent.mcp_client.get_available_tools()

        console.print(Panel(
            f"[bold]Discovery Agent Status[/bold]\n\n"
            f"[bold]LLM:[/bold]\n"
            f"  Provider: {config.llm.provider}\n"
            f"  Available: {'✓ Yes' if agent. llm_available else '✗ No'}\n"
            f"  Model: {agent.llm.model if agent.llm_available else 'N/A'}\n\n"
            f"[bold]MCP Client:[/bold]\n"
            f"  Tools Available: {len(tools)}\n"
            f"  Tools: {', '.join(tools[:5])}...\n\n"
            f"[bold]Configuration:[/bold]\n"
            f"  Interval: {config.discovery.interval_minutes} minutes",
            title="Agent Status",
            border_style="cyan"
        ))

    asyncio. run(_status())


@cli.command()
def tools():
    """List available MCP tools."""

    async def _tools():
        agent = DiscoveryAgent()
        tool_list = agent.mcp_client.get_tool_descriptions()

        table = Table(title=f"Available MCP Tools ({len(tool_list)})")
        table. add_column("Tool", style="cyan")
        table.add_column("Description", style="white")

        for tool in tool_list:
            desc = tool["description"][:60] + "..." if len(tool["description"]) > 60 else tool["description"]
            table.add_row(tool["name"], desc)

        console.print(table)

    asyncio.run(_tools())


@cli.command()
def anomalies():
    """Show active anomalies."""

    async def _anomalies():
        agent = DiscoveryAgent()
        active = await agent.get_active_anomalies()

        if not active:
            console.print("[green]✓ No active anomalies[/green]")
            return

        table = Table(title=f"Active Anomalies ({len(active)})")
        table.add_column("ID", style="cyan")
        table. add_column("Type", style="yellow")
        table. add_column("Severity", style="red")
        table. add_column("Node", style="green")

        for a in active:
            table.add_row(a["id"], a["type"], a["severity"], a["node_id"])

        console.print(table)

    asyncio.run(_anomalies())


@cli.command()
@click.argument("node_id")
@click.argument("anomaly_type")
@click.option("--severity", "-s", default="medium", help="Severity level")
def inject(node_id: str, anomaly_type: str, severity: str):
    """Inject a test anomaly."""

    async def _inject():
        agent = DiscoveryAgent()
        result = await agent. inject_test_anomaly(node_id, anomaly_type, severity)

        if "error" in result:
            console.print(f"[red]✗ Failed: {result['error']}[/red]")
        else:
            console.print(f"[green]✓ Injected {anomaly_type} on {node_id}[/green]")
            console.print(f"  Anomaly ID: {result.get('anomaly', {}).get('id', 'N/A')}")

    asyncio.run(_inject())


@cli.command()
def clear():
    """Clear all anomalies."""

    async def _clear():
        agent = DiscoveryAgent()
        result = await agent.clear_anomalies()

        if "error" in result:
            console.print(f"[red]✗ Failed: {result['error']}[/red]")
        else:
            console. print(f"[green]✓ {result. get('message', 'Cleared')}[/green]")

    asyncio.run(_clear())


def _display_report(report, verbose: bool = False):
    """Display a full diagnosis report."""
    status_display = {
        IssueSeverity. CRITICAL: ("🔴", "red bold"),
        IssueSeverity.HIGH: ("🟠", "red"),
        IssueSeverity.MEDIUM: ("🟡", "yellow"),
        IssueSeverity.LOW: ("🟢", "green"),
        IssueSeverity. HEALTHY: ("✅", "green"),
    }

    emoji, color = status_display.get(report. overall_status, ("❓", "white"))

    console.print(Panel(
        f"{emoji} [bold]Status: [{color}]{report. overall_status.value. upper()}[/{color}][/bold]\n\n"
        f"ID: {report.id}\n"
        f"Scope: {report.scope}\n"
        f"Nodes: {report.nodes_analyzed}\n"
        f"Method: {report.analysis_method}\n"
        f"Duration: {report.analysis_duration_ms}ms\n"
        f"Tool Calls: {report.tool_calls_made}\n\n"
        f"[bold]Issues:[/bold] {len(report. issues)}\n"
        f"  Critical: {report.critical_count} | High: {report. high_count} | "
        f"Medium: {report.medium_count} | Low: {report.low_count}",
        title="Diagnosis Report",
        border_style=color
    ))

    if report.summary:
        console. print(f"\n[bold]Summary:[/bold] {report.summary}")

    if report.issues:
        table = Table(title="Detected Issues")
        table.add_column("#", style="dim")
        table. add_column("Severity")
        table.add_column("Type", style="cyan")
        table. add_column("Node", style="green")
        table.add_column("Description")

        for i, issue in enumerate(report.issues, 1):
            sev_style = {"critical": "red bold", "high": "red", "medium": "yellow", "low": "green"}.get(issue. severity. value, "white")
            table.add_row(
                str(i),
                f"[{sev_style}]{issue.severity.value}[/{sev_style}]",
                issue.issue_type. value,
                issue.node_name or issue.node_id,
                issue.description[:50] + "..." if len(issue.description) > 50 else issue.description,
            )

        console.print(table)

    if report.root_cause_analysis:
        console. print(Panel(report.root_cause_analysis, title="Root Cause Analysis", border_style="magenta"))

    if report. recommendations:
        console.print("\n[bold]Recommendations:[/bold]")
        for i, rec in enumerate(report.recommendations, 1):
            console.print(f"  {i}.  {rec}")


def _display_report_summary(report):
    """Display brief summary."""
    status_display = {
        IssueSeverity.CRITICAL: ("🔴", "red"),
        IssueSeverity.HIGH: ("🟠", "red"),
        IssueSeverity. MEDIUM: ("🟡", "yellow"),
        IssueSeverity.LOW: ("🟢", "green"),
        IssueSeverity.HEALTHY: ("✅", "green"),
    }

    emoji, color = status_display.get(report. overall_status, ("❓", "white"))

    console.print(
        f"{emoji} [{color}]{report. overall_status.value.upper()}[/{color}] | "
        f"Issues: {len(report.issues)} "
        f"(C:{report.critical_count} H:{report.high_count} M:{report.medium_count} L:{report. low_count}) | "
        f"Tools: {report.tool_calls_made} | "
        f"Duration: {report.analysis_duration_ms}ms"
    )

    for issue in report.issues[:3]:
        console.print(f"  • [{issue.severity.value}] {issue.issue_type.value} on {issue.node_name or issue.node_id}")


if __name__ == "__main__":
    cli()