"""
Policy Agent CLI Runner

Command-line interface for the Policy Agent.
"""

import asyncio
import json
from datetime import datetime
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.agents.policy.agent import PolicyAgent
from src.agents.policy.models import ActionPriority
from src.agents.discovery.agent import DiscoveryAgent
from src.agents.config import config

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Policy Agent CLI

    Evaluate policies and recommend actions based on network diagnosis.
    """
    pass


@cli.command()
@click.option("--no-llm", is_flag=True, help="Skip LLM analysis")
@click.option("--output", "-o", type=click.Path(), help="Save recommendation to JSON file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def run(no_llm: bool, output: Optional[str], verbose: bool):
    """Run policy evaluation (runs discovery first if needed)."""

    async def _run():
        console.print(Panel(
            "[bold]Policy Agent (MCP-based)[/bold]\n"
            "Will run Discovery Agent first, then evaluate policies",
            title="Starting Policy Evaluation",
            border_style="blue"
        ))

        # Step 1: Run Discovery
        console.print("\n[bold]Step 1: Running Discovery Agent.. .[/bold]")
        discovery_agent = DiscoveryAgent()
        discovery_result = await discovery_agent.run(use_llm=not no_llm)

        if not discovery_result.success:
            console.print(f"[red]✗ Discovery failed: {discovery_result.error}[/red]")
            return

        diagnosis = discovery_result.result
        console.print(f"[green]✓ Discovery complete:  {len(diagnosis.issues)} issues found[/green]")

        # Step 2: Run Policy Evaluation
        console.print("\n[bold]Step 2: Running Policy Agent...[/bold]")
        policy_agent = PolicyAgent()

        if policy_agent.llm_available:
            console.print(f"[green]✓ LLM available:  {policy_agent.llm.provider_name}[/green]")
        else:
            console.print("[yellow]⚠ LLM not available, using rule-based evaluation[/yellow]")

        result = await policy_agent.evaluate(diagnosis, use_llm=not no_llm)

        if result.success:
            recommendation = result.result
            _display_recommendation(recommendation, verbose)

            if output:
                with open(output, "w") as f:
                    json.dump(recommendation.to_dict(), f, indent=2)
                console.print(f"\n[green]✓ Recommendation saved to {output}[/green]")
        else:
            console.print(f"[red]✗ Policy evaluation failed: {result.error}[/red]")

    asyncio.run(_run())


@cli.command()
@click.argument("issue_type")
@click.argument("severity")
@click.argument("node_id")
@click.option("--node-type", "-t", default="", help="Node type (e.g., router_core)")
@click.option("--no-llm", is_flag=True, help="Skip LLM analysis")
def evaluate(issue_type: str, severity: str, node_id: str, node_type: str, no_llm: bool):
    """Evaluate policies for a single issue."""

    async def _evaluate():
        console.print(Panel(
            f"[bold]Evaluating Policy for Single Issue[/bold]\n\n"
            f"Issue Type: {issue_type}\n"
            f"Severity: {severity}\n"
            f"Node:  {node_id}\n"
            f"Node Type: {node_type or 'Not specified'}",
            title="Policy Evaluation",
            border_style="blue"
        ))

        agent = PolicyAgent()
        result = await agent.evaluate_single_issue(
            issue_type=issue_type,
            severity=severity,
            node_id=node_id,
            node_type=node_type,
        )

        if result.success:
            _display_recommendation(result.result, verbose=True)
        else:
            console.print(f"[red]✗ Evaluation failed: {result.error}[/red]")

    asyncio.run(_evaluate())


@cli.command()
def policies():
    """List all active policies."""

    async def _policies():
        agent = PolicyAgent()
        policies_list = await agent.get_all_policies()

        if not policies_list:
            console.print("[yellow]No active policies found[/yellow]")
            return

        table = Table(title=f"Active Policies ({len(policies_list)})")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Type", style="yellow")
        table.add_column("Priority", style="green")

        for policy in policies_list:
            table.add_row(
                policy.get("id", ""),
                policy.get("name", ""),
                policy.get("type", ""),
                str(policy.get("priority", "")),
            )

        console.print(table)

    asyncio.run(_policies())


@cli.command()
@click.argument("policy_id")
def policy(policy_id: str):
    """Show details for a specific policy."""

    async def _policy():
        agent = PolicyAgent()
        details = await agent.get_policy_details(policy_id)

        if not details:
            console.print(f"[red]Policy '{policy_id}' not found[/red]")
            return

        console.print(Panel(
            f"[bold]{details.get('name', 'Unknown')}[/bold]\n\n"
            f"ID: {details.get('id', '')}\n"
            f"Type: {details.get('type', '')}\n"
            f"Status: {details.get('status', '')}\n"
            f"Priority: {details.get('priority', '')}\n"
            f"Description: {details.get('description', '')}\n\n"
            f"[bold]Conditions:[/bold]\n"
            + "\n".join([f"  - {c.get('field', '')} {c.get('operator', '')} {c.get('value', '')}"
                         for c in details.get('conditions', [])]) +
            f"\n\n[bold]Actions:[/bold]\n"
            + "\n".join([f"  - {a.get('type', 'Unknown')}"
                         for a in details.get('actions', [])]),
            title=f"Policy:  {policy_id}",
            border_style="cyan"
        ))

    asyncio.run(_policy())


@cli.command()
def status():
    """Show agent status."""

    async def _status():
        agent = PolicyAgent()

        tools = agent.mcp_client.get_available_tools()
        policy_tools = [t for t in tools if "polic" in t.lower() or t in ["validate_action", "get_compliance_rules"]]

        console.print(Panel(
            f"[bold]Policy Agent Status[/bold]\n\n"
            f"[bold]LLM:[/bold]\n"
            f"  Provider: {config.llm.provider}\n"
            f"  Available:  {'✓ Yes' if agent.llm_available else '✗ No'}\n"
            f"  Model: {agent.llm.model if agent.llm_available else 'N/A'}\n\n"
            f"[bold]MCP Client:[/bold]\n"
            f"  Total Tools: {len(tools)}\n"
            f"  Policy Tools: {', '.join(policy_tools)}",
            title="Agent Status",
            border_style="cyan"
        ))

    asyncio.run(_status())


def _display_recommendation(rec, verbose: bool = False):
    """Display a policy recommendation."""
    priority_display = {
        ActionPriority.IMMEDIATE: ("🚨", "red bold"),
        ActionPriority.HIGH: ("⚠️", "red"),
        ActionPriority.NORMAL: ("📋", "yellow"),
        ActionPriority.LOW: ("📝", "green"),
        ActionPriority.DEFERRED: ("📅", "dim"),
    }

    emoji, color = priority_display.get(rec.overall_priority, ("❓", "white"))

    # Summary panel
    console.print(Panel(
        f"{emoji} [bold]Priority: [{color}]{rec.overall_priority.value.upper()}[/{color}][/bold]\n\n"
        f"Recommendation ID: {rec.id}\n"
        f"Diagnosis ID: {rec.diagnosis_id}\n"
        f"Issues Evaluated: {rec.issues_evaluated}\n"
        f"Policies Matched: {len(rec.matched_policies)}\n"
        f"Actions Recommended:  {len(rec.recommended_actions)}\n"
        f"Duration: {rec.analysis_duration_ms}ms\n"
        f"Tool Calls:  {rec.tool_calls_made}",
        title="Policy Recommendation",
        border_style=color
    ))

    if rec.summary:
        console.print(f"\n[bold]Summary:[/bold] {rec.summary}")

    if rec.reasoning and verbose:
        console.print(f"\n[bold]Reasoning:[/bold] {rec.reasoning}")

    # Matched policies
    if rec.matched_policies:
        console.print("\n[bold]Matched Policies:[/bold]")
        for policy in rec.matched_policies:
            console.print(f"  • {policy.policy_name} ({policy.policy_id})")

    # Recommended actions
    if rec.recommended_actions:
        table = Table(title="Recommended Actions")
        table.add_column("#", style="dim")
        table.add_column("Priority")
        table.add_column("Action", style="cyan")
        table.add_column("Target", style="green")
        table.add_column("Reason")

        for i, action in enumerate(rec.recommended_actions, 1):
            priority_style = {
                "immediate": "red bold",
                "high": "red",
                "normal": "yellow",
                "low": "green",
                "deferred": "dim",
            }.get(action.priority.value, "white")

            table.add_row(
                str(i),
                f"[{priority_style}]{action.priority.value}[/{priority_style}]",
                action.action_type,
                action.target_node_name or action.target_node_id,
                action.reason[: 40] + "..." if len(action.reason) > 40 else action.reason,
            )

        console.print(table)

        # Detailed actions if verbose
        if verbose:
            for action in rec.recommended_actions:
                console.print(f"\n[bold]{action.action_type}[/bold] on {action.target_node_name}")
                console.print(f"  Policy: {action.source_policy_name}")
                console.print(f"  Issue: {action.source_issue_type}")
                console.print(f"  Reason: {action.reason}")
                if action.expected_outcome:
                    console.print(f"  Expected: {action.expected_outcome}")
                if action.requires_approval:
                    console.print(f"  [yellow]⚠ Requires approval[/yellow]")


if __name__ == "__main__":
    cli()