"""
Compliance Agent CLI Runner

Command-line interface for the Compliance Agent.
"""

import asyncio
import json
from datetime import datetime
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.agents.compliance.agent import ComplianceAgent
from src.agents.compliance.models import ValidationStatus
from src.agents.policy.agent import PolicyAgent
from src.agents.discovery.agent import DiscoveryAgent
from src.agents.config import config

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Compliance Agent CLI

    Validate actions against compliance rules before execution.
    """
    pass


@cli.command()
@click.option("--no-llm", is_flag=True, help="Skip LLM analysis")
@click.option("--output", "-o", type=click.Path(), help="Save result to JSON file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def run(no_llm: bool, output: Optional[str], verbose: bool):
    """Run full pipeline:  Discovery → Policy → Compliance."""

    async def _run():
        console.print(Panel(
            "[bold]Compliance Agent (MCP-based)[/bold]\n"
            "Will run Discovery → Policy → Compliance pipeline",
            title="Starting Compliance Validation",
            border_style="blue"
        ))

        # Step 1: Run Discovery
        console.print("\n[bold]Step 1: Running Discovery Agent.. .[/bold]")
        discovery_agent = DiscoveryAgent()
        discovery_result = await discovery_agent.run(use_llm=not no_llm)

        if not discovery_result.success:
            console.print(f"[red]✗ Discovery failed:  {discovery_result.error}[/red]")
            return

        diagnosis = discovery_result.result
        console.print(f"[green]✓ Discovery complete: {len(diagnosis.issues)} issues found[/green]")

        # Step 2: Run Policy
        console.print("\n[bold]Step 2: Running Policy Agent...[/bold]")
        policy_agent = PolicyAgent()
        policy_result = await policy_agent.evaluate(diagnosis, use_llm=not no_llm)

        if not policy_result.success:
            console.print(f"[red]✗ Policy evaluation failed: {policy_result.error}[/red]")
            return

        recommendation = policy_result.result
        console.print(
            f"[green]✓ Policy complete: {len(recommendation.recommended_actions)} actions recommended[/green]")

        # Step 3: Run Compliance
        console.print("\n[bold]Step 3: Running Compliance Agent...[/bold]")
        compliance_agent = ComplianceAgent()

        if compliance_agent.llm_available:
            console.print(f"[green]✓ LLM available: {compliance_agent.llm.provider_name}[/green]")
        else:
            console.print("[yellow]⚠ LLM not available, using rule-based validation[/yellow]")

        result = await compliance_agent.validate(recommendation, use_llm=not no_llm)

        if result.success:
            compliance_result = result.result
            _display_compliance_result(compliance_result, verbose)

            if output:
                with open(output, "w") as f:
                    json.dump(compliance_result.to_dict(), f, indent=2)
                console.print(f"\n[green]✓ Result saved to {output}[/green]")
        else:
            console.print(f"[red]✗ Compliance validation failed: {result.error}[/red]")

    asyncio.run(_run())


@cli.command()
@click.argument("action_type")
@click.argument("target_node_id")
@click.option("--reason", "-r", default="Manual validation", help="Reason for action")
@click.option("--no-llm", is_flag=True, help="Skip LLM analysis")
def validate(action_type: str, target_node_id: str, reason: str, no_llm: bool):
    """Validate a single action."""

    async def _validate():
        console.print(Panel(
            f"[bold]Validating Single Action[/bold]\n\n"
            f"Action:  {action_type}\n"
            f"Target: {target_node_id}\n"
            f"Reason: {reason}",
            title="Compliance Validation",
            border_style="blue"
        ))

        agent = ComplianceAgent()
        result = await agent.validate_single_action(
            action_type=action_type,
            target_node_id=target_node_id,
            reason=reason,
        )

        if result.success:
            _display_compliance_result(result.result, verbose=True)
        else:
            console.print(f"[red]✗ Validation failed: {result.error}[/red]")

    asyncio.run(_validate())


@cli.command()
def rules():
    """List all compliance rules."""

    async def _rules():
        agent = ComplianceAgent()
        rules_list = await agent.get_compliance_rules()

        if not rules_list:
            console.print("[yellow]No compliance rules found[/yellow]")
            return

        table = Table(title=f"Compliance Rules ({len(rules_list)})")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Type", style="yellow")
        table.add_column("Enforcement", style="red")

        for rule in rules_list:
            table.add_row(
                rule.get("id", ""),
                rule.get("name", ""),
                rule.get("check_type", ""),
                rule.get("enforcement", ""),
            )

        console.print(table)

    asyncio.run(_rules())


@cli.command()
def window():
    """Check if in maintenance window."""

    async def _window():
        agent = ComplianceAgent()
        in_window = await agent.check_maintenance_window()
        current_time = datetime.utcnow()

        if in_window:
            console.print(Panel(
                f"[green]✓ IN MAINTENANCE WINDOW[/green]\n\n"
                f"Current Time (UTC): {current_time.strftime('%H:%M')}\n"
                f"Window:  {agent.checker.maintenance_window_start}:00 - {agent.checker.maintenance_window_end}: 00 UTC\n\n"
                f"High-impact actions are permitted.",
                title="Maintenance Window Status",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"[yellow]⚠ OUTSIDE MAINTENANCE WINDOW[/yellow]\n\n"
                f"Current Time (UTC): {current_time.strftime('%H:%M')}\n"
                f"Window:  {agent.checker.maintenance_window_start}:00 - {agent.checker.maintenance_window_end}:00 UTC\n\n"
                f"High-impact actions may be restricted.",
                title="Maintenance Window Status",
                border_style="yellow"
            ))

    asyncio.run(_window())


@cli.command()
def status():
    """Show agent status."""

    async def _status():
        agent = ComplianceAgent()
        current_time = datetime.utcnow()
        in_window = await agent.check_maintenance_window()

        tools = agent.mcp_client.get_available_tools()
        compliance_tools = [t for t in tools if
                            t in ["validate_action", "get_compliance_rules", "get_execution_history"]]

        console.print(Panel(
            f"[bold]Compliance Agent Status[/bold]\n\n"
            f"[bold]LLM:[/bold]\n"
            f"  Provider: {config.llm.provider}\n"
            f"  Available: {'✓ Yes' if agent.llm_available else '✗ No'}\n"
            f"  Model: {agent.llm.model if agent.llm_available else 'N/A'}\n\n"
            f"[bold]MCP Client:[/bold]\n"
            f"  Total Tools: {len(tools)}\n"
            f"  Compliance Tools: {', '.join(compliance_tools)}\n\n"
            f"[bold]Maintenance Window:[/bold]\n"
            f"  Window: {agent.checker.maintenance_window_start}:00 - {agent.checker.maintenance_window_end}:00 UTC\n"
            f"  Current Time (UTC): {current_time.strftime('%H:%M')}\n"
            f"  In Window:  {'✓ Yes' if in_window else '✗ No'}\n\n"
            f"[bold]Rate Limits:[/bold]\n"
            f"  Max Actions/Hour/Node: {agent.checker.rate_limit_per_hour}",
            title="Agent Status",
            border_style="cyan"
        ))

    asyncio.run(_status())


def _display_compliance_result(result, verbose: bool = False):
    """Display a compliance result."""

    # Determine overall status display
    if result.all_approved:
        emoji = "✅"
        status = "ALL APPROVED"
        color = "green"
    elif result.denied_count > 0:
        emoji = "❌"
        status = "HAS DENIALS"
        color = "red"
    elif result.pending_count > 0:
        emoji = "⏳"
        status = "PENDING APPROVAL"
        color = "yellow"
    else:
        emoji = "📋"
        status = "PROCESSED"
        color = "blue"

    # Summary panel
    console.print(Panel(
        f"{emoji} [bold]Status:  [{color}]{status}[/{color}][/bold]\n\n"
        f"Compliance ID: {result.id}\n"
        f"Recommendation ID: {result.recommendation_id}\n"
        f"Total Actions: {result.total_actions}\n"
        f"Duration: {result.analysis_duration_ms}ms\n"
        f"Tool Calls: {result.tool_calls_made}\n\n"
        f"[bold]Results:[/bold]\n"
        f"  ✓ Approved: {result.approved_count}\n"
        f"  ✗ Denied: {result.denied_count}\n"
        f"  ⏳ Pending: {result.pending_count}\n"
        f"  📅 Deferred: {result.deferred_count}",
        title="Compliance Result",
        border_style=color
    ))

    if result.summary:
        console.print(f"\n[bold]Summary:[/bold] {result.summary}")

    if result.reasoning and verbose:
        console.print(f"\n[bold]Reasoning:[/bold] {result.reasoning}")

    # Validations table
    if result.validations:
        table = Table(title="Action Validations")
        table.add_column("#", style="dim")
        table.add_column("Status")
        table.add_column("Action", style="cyan")
        table.add_column("Target", style="green")
        table.add_column("Violations", style="red")
        table.add_column("Warnings", style="yellow")

        for i, validation in enumerate(result.validations, 1):
            status_display = {
                ValidationStatus.APPROVED: ("[green]✓ APPROVED[/green]", "green"),
                ValidationStatus.DENIED: ("[red]✗ DENIED[/red]", "red"),
                ValidationStatus.PENDING_APPROVAL: ("[yellow]⏳ PENDING[/yellow]", "yellow"),
                ValidationStatus.DEFERRED: ("[blue]📅 DEFERRED[/blue]", "blue"),
            }

            status_text, _ = status_display.get(
                validation.status,
                (validation.status.value, "white")
            )

            table.add_row(
                str(i),
                status_text,
                validation.action_type,
                validation.target_node_name or validation.target_node_id,
                str(len(validation.violations)),
                str(len(validation.warnings)),
            )

        console.print(table)

    # Show violations if verbose
    if verbose:
        for validation in result.validations:
            if validation.violations:
                console.print(
                    f"\n[bold red]Violations for {validation.action_type} on {validation.target_node_name}:[/bold red]")
                for violation in validation.violations:
                    blocking_text = "[red](BLOCKING)[/red]" if violation.blocking else "[yellow](WARNING)[/yellow]"
                    console.print(f"  • {blocking_text} {violation.rule_name}")
                    console.print(f"    {violation.description}")
                    if violation.resolution_options:
                        console.print(f"    Resolution options:")
                        for opt in violation.resolution_options[: 2]:
                            console.print(f"      - {opt}")

            if validation.warnings:
                console.print(f"\n[bold yellow]Warnings for {validation.action_type}:[/bold yellow]")
                for warning in validation.warnings:
                    console.print(f"  • {warning}")

    # Show approved actions ready for execution
    approved = result.get_approved_actions()
    if approved:
        console.print(f"\n[bold green]✓ {len(approved)} action(s) ready for execution:[/bold green]")
        for action in approved:
            console.print(f"  • {action.action_type} on {action.target_node_name or action.target_node_id}")

    # Show denied actions
    denied = result.get_denied_actions()
    if denied:
        console.print(f"\n[bold red]✗ {len(denied)} action(s) denied:[/bold red]")
        for action in denied:
            console.print(f"  • {action.action_type} on {action.target_node_name or action.target_node_id}")
            console.print(f"    Reason: {action.denial_reason}")


if __name__ == "__main__":
    cli()