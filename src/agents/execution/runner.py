"""
Execution Agent CLI Runner

Command-line interface for the Execution Agent.
"""

import asyncio
import json
from datetime import datetime
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.agents.execution.agent import ExecutionAgent
from src.agents.execution.models import ExecutionStatus, VerificationStatus
from src.agents.compliance.agent import ComplianceAgent
from src.agents.policy.agent import PolicyAgent
from src.agents.discovery.agent import DiscoveryAgent
from src.agents.config import config

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Execution Agent CLI

    Execute approved actions on the network.
    """
    pass


@cli.command()
@click.option("--no-verify", is_flag=True, help="Skip post-execution verification")
@click.option("--dry-run", is_flag=True, help="Simulate execution without actually executing")
@click.option("--no-llm", is_flag=True, help="Skip LLM analysis in earlier stages")
@click.option("--output", "-o", type=click.Path(), help="Save result to JSON file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def run(no_verify: bool, dry_run: bool, no_llm: bool, output: Optional[str], verbose: bool):
    """Run full pipeline: Discovery → Policy → Compliance → Execution."""

    async def _run():
        console.print(Panel(
            "[bold]Execution Agent (MCP-based)[/bold]\n"
            f"Mode: {'DRY RUN' if dry_run else 'LIVE EXECUTION'}\n"
            f"Verification: {'Disabled' if no_verify else 'Enabled'}\n"
            "Will run full pipeline:  Discovery → Policy → Compliance → Execution",
            title="Starting Execution Pipeline",
            border_style="red" if not dry_run else "yellow"
        ))

        if not dry_run:
            console.print("[bold red]⚠️  LIVE EXECUTION MODE - Actions will be performed![/bold red]\n")

        # Step 1: Discovery
        console.print("[bold]Step 1: Running Discovery Agent.. .[/bold]")
        discovery_agent = DiscoveryAgent()
        discovery_result = await discovery_agent.run(use_llm=not no_llm)

        if not discovery_result.success:
            console.print(f"[red]✗ Discovery failed: {discovery_result.error}[/red]")
            return

        diagnosis = discovery_result.result
        console.print(f"[green]✓ Discovery complete:  {len(diagnosis.issues)} issues found[/green]")

        if not diagnosis.issues:
            console.print("[yellow]No issues found, nothing to execute.[/yellow]")
            return

        # Step 2: Policy
        console.print("\n[bold]Step 2: Running Policy Agent...[/bold]")
        policy_agent = PolicyAgent()
        policy_result = await policy_agent.evaluate(diagnosis, use_llm=not no_llm)

        if not policy_result.success:
            console.print(f"[red]✗ Policy evaluation failed: {policy_result.error}[/red]")
            return

        recommendation = policy_result.result
        console.print(
            f"[green]✓ Policy complete: {len(recommendation.recommended_actions)} actions recommended[/green]")

        if not recommendation.recommended_actions:
            console.print("[yellow]No actions recommended, nothing to execute.[/yellow]")
            return

        # Step 3: Compliance
        console.print("\n[bold]Step 3: Running Compliance Agent...[/bold]")
        compliance_agent = ComplianceAgent()
        compliance_result = await compliance_agent.validate(recommendation, use_llm=not no_llm)

        if not compliance_result.success:
            console.print(f"[red]✗ Compliance validation failed: {compliance_result.error}[/red]")
            return

        compliance = compliance_result.result
        approved_count = compliance.approved_count
        console.print(
            f"[green]✓ Compliance complete: {approved_count}/{compliance.total_actions} actions approved[/green]")

        if approved_count == 0:
            console.print("[yellow]No actions approved, nothing to execute.[/yellow]")
            return

        # Step 4: Execution
        console.print("\n[bold]Step 4: Running Execution Agent...[/bold]")
        execution_agent = ExecutionAgent()

        if execution_agent.llm_available:
            console.print(f"[green]✓ LLM available:  {execution_agent.llm.provider_name}[/green]")

        with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
        ) as progress:
            task = progress.add_task(
                f"Executing {approved_count} actions..." if not dry_run else f"Simulating {approved_count} actions.. .",
                total=None
            )

            result = await execution_agent.execute(
                compliance,
                verify=not no_verify,
                dry_run=dry_run,
            )

            progress.remove_task(task)

        if result.success:
            execution_result = result.result
            _display_execution_result(execution_result, verbose)

            if output:
                with open(output, "w") as f:
                    json.dump(execution_result.to_dict(), f, indent=2)
                console.print(f"\n[green]✓ Result saved to {output}[/green]")
        else:
            console.print(f"[red]✗ Execution failed: {result.error}[/red]")

    asyncio.run(_run())


@cli.command()
@click.argument("action_type")
@click.argument("target_node_id")
@click.option("--reason", "-r", default="Manual execution", help="Reason for action")
@click.option("--no-verify", is_flag=True, help="Skip verification")
@click.option("--dry-run", is_flag=True, help="Simulate execution")
def execute(action_type: str, target_node_id: str, reason: str, no_verify: bool, dry_run: bool):
    """Execute a single action directly (bypasses pipeline)."""

    async def _execute():
        console.print(Panel(
            f"[bold]Direct Action Execution[/bold]\n\n"
            f"Action:  {action_type}\n"
            f"Target: {target_node_id}\n"
            f"Reason: {reason}\n"
            f"Mode: {'DRY RUN' if dry_run else 'LIVE'}",
            title="Execution",
            border_style="red" if not dry_run else "yellow"
        ))

        if not dry_run:
            console.print("[bold red]⚠️  This will execute without compliance check![/bold red]")
            if not click.confirm("Are you sure you want to proceed?"):
                console.print("[yellow]Cancelled.[/yellow]")
                return

        agent = ExecutionAgent()
        result = await agent.execute_single_action(
            action_type=action_type,
            target_node_id=target_node_id,
            reason=reason,
            verify=not no_verify,
            dry_run=dry_run,
        )

        if result.success:
            _display_execution_result(result.result, verbose=True)
        else:
            console.print(f"[red]✗ Execution failed: {result.error}[/red]")

    asyncio.run(_execute())


@cli.command()
@click.option("--limit", "-l", default=20, help="Number of records to show")
def history(limit: int):
    """Show execution history."""

    async def _history():
        agent = ExecutionAgent()
        executions = await agent.get_execution_history(limit=limit)

        if not executions:
            console.print("[yellow]No execution history found[/yellow]")
            return

        table = Table(title=f"Execution History (Last {len(executions)})")
        table.add_column("ID", style="cyan")
        table.add_column("Action", style="white")
        table.add_column("Target", style="green")
        table.add_column("Status", style="bold")
        table.add_column("Duration", style="dim")
        table.add_column("Time", style="dim")

        for exec_data in executions:
            status = exec_data.get("status", "unknown")
            status_style = {
                "SUCCESS": "[green]✓ SUCCESS[/green]",
                "FAILED": "[red]✗ FAILED[/red]",
            }.get(status, status)

            table.add_row(
                exec_data.get("execution_id", "")[: 12],
                exec_data.get("action_type", ""),
                exec_data.get("target_node_id", ""),
                status_style,
                f"{exec_data.get('duration_ms', 'N/A')}ms",
                exec_data.get("completed_at", "")[:19],
            )

        console.print(table)

    asyncio.run(_history())


@cli.command()
def status():
    """Show agent status."""

    async def _status():
        agent = ExecutionAgent()

        tools = agent.mcp_client.get_available_tools()
        execution_tools = [t for t in tools if t in ["execute_action", "get_execution_status", "get_execution_history"]]

        console.print(Panel(
            f"[bold]Execution Agent Status[/bold]\n\n"
            f"[bold]LLM:[/bold]\n"
            f"  Provider: {config.llm.provider}\n"
            f"  Available:  {'✓ Yes' if agent.llm_available else '✗ No'}\n"
            f"  Model: {agent.llm.model if agent.llm_available else 'N/A'}\n\n"
            f"[bold]MCP Client:[/bold]\n"
            f"  Total Tools: {len(tools)}\n"
            f"  Execution Tools: {', '.join(execution_tools)}\n\n"
            f"[bold]Settings:[/bold]\n"
            f"  Verify After Execution: {agent.verify_after_execution}\n"
            f"  Retry On Failure: {agent.retry_on_failure}\n"
            f"  Max Retries: {agent.max_retries}\n"
            f"  Retry Delay: {agent.retry_delay_seconds}s",
            title="Agent Status",
            border_style="cyan"
        ))

    asyncio.run(_status())


def _display_execution_result(result, verbose: bool = False):
    """Display an execution result."""

    # Determine overall status display
    if result.all_successful:
        emoji = "✅"
        status = "ALL SUCCESSFUL"
        color = "green"
    elif result.has_failures:
        emoji = "❌"
        status = "HAS FAILURES"
        color = "red"
    elif result.skipped_count == result.total_actions:
        emoji = "⏭️"
        status = "ALL SKIPPED"
        color = "yellow"
    else:
        emoji = "📋"
        status = "COMPLETED"
        color = "blue"

    # Summary panel
    console.print(Panel(
        f"{emoji} [bold]Status:  [{color}]{status}[/{color}][/bold]\n\n"
        f"Execution ID: {result.id}\n"
        f"Compliance Result: {result.compliance_result_id}\n"
        f"Total Actions: {result.total_actions}\n"
        f"Duration: {result.total_duration_ms}ms\n"
        f"Tool Calls: {result.tool_calls_made}\n\n"
        f"[bold]Results:[/bold]\n"
        f"  ✓ Successful: {result.success_count}\n"
        f"  ✗ Failed: {result.failed_count}\n"
        f"  ⏭️ Skipped:  {result.skipped_count}\n"
        f"  ↩️ Rolled Back: {result.rolled_back_count}\n\n"
        f"[bold]Verification:[/bold]\n"
        f"  Performed: {'Yes' if result.verification_performed else 'No'}\n"
        f"  Verified Success: {result.verification_success_count}/{result.total_actions}",
        title="Execution Result",
        border_style=color
    ))

    if result.summary:
        console.print(f"\n[bold]Summary:[/bold] {result.summary}")

    # Executions table
    if result.executions:
        table = Table(title="Action Executions")
        table.add_column("#", style="dim")
        table.add_column("Status")
        table.add_column("Action", style="cyan")
        table.add_column("Target", style="green")
        table.add_column("Duration", style="dim")
        table.add_column("Verified")

        for i, execution in enumerate(result.executions, 1):
            status_display = {
                ExecutionStatus.SUCCESS: "[green]✓ SUCCESS[/green]",
                ExecutionStatus.FAILED: "[red]✗ FAILED[/red]",
                ExecutionStatus.SKIPPED: "[yellow]⏭️ SKIPPED[/yellow]",
                ExecutionStatus.ROLLED_BACK: "[magenta]↩️ ROLLED BACK[/magenta]",
                ExecutionStatus.IN_PROGRESS: "[blue]⏳ IN PROGRESS[/blue]",
                ExecutionStatus.PENDING: "[dim]⏸️ PENDING[/dim]",
            }.get(execution.status, execution.status.value)

            verification_display = {
                VerificationStatus.VERIFIED_SUCCESS: "[green]✓[/green]",
                VerificationStatus.VERIFIED_FAILED: "[red]✗[/red]",
                VerificationStatus.VERIFICATION_ERROR: "[yellow]⚠[/yellow]",
                VerificationStatus.NOT_VERIFIED: "[dim]-[/dim]",
            }.get(execution.verification.status, "-")

            table.add_row(
                str(i),
                status_display,
                execution.action_type,
                execution.target_node_name or execution.target_node_id,
                f"{execution.duration_ms}ms" if execution.duration_ms else "-",
                verification_display,
            )

        console.print(table)

    # Show details if verbose
    if verbose:
        for execution in result.executions:
            console.print(f"\n[bold]{execution.action_type}[/bold] on {execution.target_node_name}")
            console.print(f"  ID: {execution.id}")
            console.print(f"  Status: {execution.status.value}")

            if execution.success:
                console.print(f"  [green]Result: {execution.result_message}[/green]")
            elif execution.error_message:
                console.print(f"  [red]Error:  {execution.error_message}[/red]")

            if execution.retry_count > 0:
                console.print(f"  Retries: {execution.retry_count}")

            if execution.verification.status != VerificationStatus.NOT_VERIFIED:
                console.print(f"  Verification: {execution.verification.status.value}")
                if execution.verification.improvement_detected:
                    console.print(f"  [green]Improvement:  {execution.verification.improvement_details}[/green]")
                elif execution.verification.issues_found:
                    for issue in execution.verification.issues_found:
                        console.print(f"  [yellow]Issue: {issue}[/yellow]")

    # Show successful executions
    successful = result.get_successful_executions()
    if successful:
        console.print(f"\n[bold green]✓ {len(successful)} action(s) executed successfully:[/bold green]")
        for exec in successful:
            console.print(f"  • {exec.action_type} on {exec.target_node_name or exec.target_node_id}")

    # Show failed executions
    failed = result.get_failed_executions()
    if failed:
        console.print(f"\n[bold red]✗ {len(failed)} action(s) failed:[/bold red]")
        for exec in failed:
            console.print(f"  • {exec.action_type} on {exec.target_node_name or exec.target_node_id}")
            console.print(f"    Error: {exec.error_message}")


if __name__ == "__main__":
    cli()