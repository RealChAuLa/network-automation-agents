"""
Audit CLI

Command-line interface for audit operations.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.audit.logger import AuditLogger
from src.audit.models import AuditRecordType

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Audit CLI

    Query and manage immutable audit records.
    """
    pass


@cli.command()
def status():
    """Show audit system status."""
    audit = AuditLogger()
    audit.connect()

    stats = audit.get_stats()

    db_mode = stats.get("database", {}).get("mode", "unknown")

    console.print(Panel(
        f"[bold]Audit System Status[/bold]\n\n"
        f"[bold]Configuration:[/bold]\n"
        f"  Enabled: {'✓ Yes' if stats['enabled'] else '✗ No'}\n"
        f"  Connected: {'✓ Yes' if stats['connected'] else '✗ No'}\n"
        f"  Mode: {db_mode}\n\n"
        f"[bold]Records:[/bold]\n"
        f"  Intent Records: {stats['records']['intents']}\n"
        f"  Result Records:  {stats['records']['results']}\n"
        f"  Denial Records: {stats['records']['denials']}\n"
        f"  Total:  {stats['records']['total']}",
        title="Audit Status",
        border_style="cyan"
    ))


@cli.command()
@click.option("--type", "-t", "record_type",
              type=click.Choice(["intent", "result", "denial", "all"]),
              default="all", help="Filter by record type")
@click.option("--limit", "-l", default=20, help="Number of records to show")
@click.option("--verbose", "-v", is_flag=True, help="Show full details")
def list(record_type: str, limit: int, verbose: bool):
    """List audit records."""
    audit = AuditLogger()
    audit.connect()

    if record_type == "all":
        records = audit.query(limit=limit)
        title = "All Audit Records"
    else:
        records = audit.query(AuditRecordType(record_type), limit=limit)
        title = f"{record_type.title()} Records"

    if not records:
        console.print("[yellow]No audit records found[/yellow]")
        return

    table = Table(title=f"{title} ({len(records)})")
    table.add_column("Key", style="cyan", max_width=40)
    table.add_column("Type", style="yellow")
    table.add_column("Summary", style="white")
    table.add_column("Timestamp", style="dim")

    for record in records:
        value = record.get("value", {})
        table.add_row(
            record.get("key", "")[-30:],
            value.get("record_type", ""),
            value.get("summary", "")[:40],
            value.get("timestamp", "")[:19],
        )

    console.print(table)

    if verbose and records:
        console.print("\n[bold]Detailed Records:[/bold]")
        for record in records[: 5]:  # Show first 5 in detail
            value = record.get("value", {})
            console.print(Panel(
                json.dumps(value, indent=2, default=str),
                title=record.get("key", ""),
                border_style="dim"
            ))


@cli.command()
@click.option("--limit", "-l", default=20, help="Number of records to show")
def intents(limit: int):
    """List intent records."""
    audit = AuditLogger()
    audit.connect()

    records = audit.get_intents(limit=limit)

    if not records:
        console.print("[yellow]No intent records found[/yellow]")
        return

    table = Table(title=f"Intent Records ({len(records)})")
    table.add_column("ID", style="cyan")
    table.add_column("Action", style="yellow")
    table.add_column("Target", style="green")
    table.add_column("Reason", style="white")
    table.add_column("Approved By", style="blue")
    table.add_column("Time", style="dim")

    for record in records:
        value = record.get("value", {})
        table.add_row(
            value.get("id", "")[-12:],
            value.get("action_type", ""),
            value.get("target_node_name", "") or value.get("target_node_id", ""),
            value.get("reason", "")[:30],
            value.get("approved_by", ""),
            value.get("timestamp", "")[:19],
        )

    console.print(table)


@cli.command()
@click.option("--limit", "-l", default=20, help="Number of records to show")
def results(limit: int):
    """List result records."""
    audit = AuditLogger()
    audit.connect()

    records = audit.get_results(limit=limit)

    if not records:
        console.print("[yellow]No result records found[/yellow]")
        return

    table = Table(title=f"Result Records ({len(records)})")
    table.add_column("ID", style="cyan")
    table.add_column("Action", style="yellow")
    table.add_column("Target", style="green")
    table.add_column("Status")
    table.add_column("Duration", style="dim")
    table.add_column("Verified")
    table.add_column("Time", style="dim")

    for record in records:
        value = record.get("value", {})
        success = value.get("success", False)
        status_display = "[green]✓ SUCCESS[/green]" if success else "[red]✗ FAILED[/red]"
        verified = "[green]✓[/green]" if value.get("verified") else "[dim]-[/dim]"

        table.add_row(
            value.get("id", "")[-12:],
            value.get("action_type", ""),
            value.get("target_node_name", "") or value.get("target_node_id", ""),
            status_display,
            f"{value.get('duration_ms', '-')}ms",
            verified,
            value.get("timestamp", "")[:19],
        )

    console.print(table)


@cli.command()
@click.option("--limit", "-l", default=20, help="Number of records to show")
def denials(limit: int):
    """List denial records."""
    audit = AuditLogger()
    audit.connect()

    records = audit.get_denials(limit=limit)

    if not records:
        console.print("[green]✓ No denial records - all actions were approved![/green]")
        return

    table = Table(title=f"Denial Records ({len(records)})")
    table.add_column("ID", style="cyan")
    table.add_column("Action", style="yellow")
    table.add_column("Target", style="green")
    table.add_column("Violation", style="red")
    table.add_column("Rule", style="blue")
    table.add_column("Time", style="dim")

    for record in records:
        value = record.get("value", {})
        table.add_row(
            value.get("id", "")[-12:],
            value.get("action_type", ""),
            value.get("target_node_name", "") or value.get("target_node_id", ""),
            value.get("violation_type", ""),
            value.get("rule_name", "")[:20],
            value.get("timestamp", "")[:19],
        )

    console.print(table)


@cli.command()
@click.argument("key")
@click.option("--verify", "-v", is_flag=True, help="Verify cryptographically")
def get(key: str, verify: bool):
    """Get a specific audit record by key."""
    audit = AuditLogger()
    audit.connect()

    result = audit.get_record(key, verify=verify)

    if not result:
        console.print(f"[red]Record not found: {key}[/red]")
        return

    value = result.get("value", {})
    verified = result.get("verified", False)

    verification_status = "[green]✓ Verified[/green]" if verified else "[yellow]Not verified[/yellow]"

    console.print(Panel(
        f"[bold]Verification:[/bold] {verification_status}\n"
        f"[bold]Transaction ID:[/bold] {result.get('tx_id', 'N/A')}\n\n"
        f"[bold]Content:[/bold]\n"
        f"{json.dumps(value, indent=2, default=str)}",
        title=f"Audit Record: {key}",
        border_style="cyan"
    ))


@cli.command()
def summary():
    """Show audit summary report."""
    audit = AuditLogger()
    audit.connect()

    stats = audit.get_stats()

    # Get recent records
    recent_intents = audit.get_intents(limit=100)
    recent_results = audit.get_results(limit=100)
    recent_denials = audit.get_denials(limit=100)

    # Calculate success rate
    success_count = sum(1 for r in recent_results if r.get("value", {}).get("success"))
    total_results = len(recent_results)
    success_rate = (success_count / total_results * 100) if total_results > 0 else 0

    # Calculate verification rate
    verified_count = sum(1 for r in recent_results if r.get("value", {}).get("verified"))
    verification_rate = (verified_count / total_results * 100) if total_results > 0 else 0

    console.print(Panel(
        f"[bold]Audit Summary Report[/bold]\n\n"
        f"[bold]Total Records:[/bold]\n"
        f"  Intent Records: {stats['records']['intents']}\n"
        f"  Result Records: {stats['records']['results']}\n"
        f"  Denial Records: {stats['records']['denials']}\n"
        f"  Total: {stats['records']['total']}\n\n"
        f"[bold]Recent Performance (last 100 executions):[/bold]\n"
        f"  Success Rate: {success_rate:.1f}%\n"
        f"  Verification Rate:  {verification_rate:. 1f}%\n"
        f"  Denial Count: {len(recent_denials)}\n\n"
        f"[bold]Database:[/bold]\n"
        f"  Mode: {stats.get('database', {}).get('mode', 'unknown')}\n"
        f"  Connected: {'✓' if stats['connected'] else '✗'}",
        title="Audit Summary",
        border_style="green"
    ))


@cli.command()
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--format", "-f", "output_format",
              type=click.Choice(["json", "csv"]),
              default="json", help="Output format")
@click.option("--limit", "-l", default=1000, help="Maximum records to export")
def export(output: Optional[str], output_format: str, limit: int):
    """Export audit records."""
    audit = AuditLogger()
    audit.connect()

    records = audit.query(limit=limit)

    if not records:
        console.print("[yellow]No records to export[/yellow]")
        return

    if output_format == "json":
        data = [r.get("value", {}) for r in records]
        content = json.dumps(data, indent=2, default=str)
    else:
        # CSV format
        import csv
        import io

        output_buffer = io.StringIO()
        fieldnames = ["id", "record_type", "timestamp", "action_type",
                      "target_node_id", "success", "summary"]
        writer = csv.DictWriter(output_buffer, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()

        for record in records:
            value = record.get("value", {})
            writer.writerow(value)

        content = output_buffer.getvalue()

    if output:
        with open(output, "w") as f:
            f.write(content)
        console.print(f"[green]✓ Exported {len(records)} records to {output}[/green]")
    else:
        console.print(content)


if __name__ == "__main__":
    cli()