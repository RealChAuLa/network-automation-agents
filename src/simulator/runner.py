"""
CLI Runner for the Network Simulator

Provides command-line interface for running simulations.
"""

import json
import time
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich. console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout

from src.simulator.network_sim import NetworkSimulator
from src.simulator. log_generator import LogGenerator
from src. simulator.telemetry_generator import TelemetryGenerator
from src.simulator.anomaly_injector import AnomalyInjector
from src.models.network import AnomalyType, AnomalySeverity, NodeStatus


console = Console()


def get_simulator_components():
    """Initialize and return all simulator components."""
    network_sim = NetworkSimulator()
    network_sim.create_default_topology()

    log_gen = LogGenerator(network_sim)
    tel_gen = TelemetryGenerator(network_sim)
    anomaly_injector = AnomalyInjector(network_sim, tel_gen, log_gen)

    return network_sim, log_gen, tel_gen, anomaly_injector


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Network Automation Simulator CLI

    Generate synthetic network logs, telemetry, and anomalies for testing.
    """
    pass


@cli.command()
@click. option("--format", "output_format", type=click.Choice(["table", "json"]), default="table")
def show_topology(output_format: str):
    """Display the network topology."""
    network_sim, _, _, _ = get_simulator_components()

    if output_format == "json":
        topology_data = {
            "name": network_sim. topology. name,
            "nodes": [
                {
                    "id": n.id,
                    "name": n.name,
                    "type": n.type.value,
                    "ip": n.ip_address,
                    "status": n. status.value,
                    "vendor": n.vendor,
                    "location": n.location,
                }
                for n in network_sim.get_all_nodes()
            ],
            "links": [
                {
                    "source": l.source_node_id,
                    "target": l.target_node_id,
                    "bandwidth_mbps": l.bandwidth_mbps,
                    "latency_ms": l.latency_ms,
                }
                for l in network_sim.topology.links
            ],
        }
        console.print_json(json.dumps(topology_data, indent=2))
    else:
        # Print summary
        summary = network_sim.get_topology_summary()
        console.print(Panel(
            f"[bold]Topology:[/bold] {summary['name']}\n"
            f"[bold]Total Nodes:[/bold] {summary['total_nodes']}\n"
            f"[bold]Total Links:[/bold] {summary['total_links']}",
            title="Network Topology Summary"
        ))

        # Print nodes table
        table = Table(title="Network Nodes")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table. add_column("Type", style="yellow")
        table. add_column("IP Address", style="blue")
        table.add_column("Status", style="magenta")
        table.add_column("Vendor", style="white")

        for node in network_sim.get_all_nodes():
            status_style = {
                NodeStatus. HEALTHY: "green",
                NodeStatus.WARNING: "yellow",
                NodeStatus.CRITICAL: "red",
                NodeStatus.DOWN: "red bold",
            }. get(node.status, "white")

            table.add_row(
                node. id,
                node.name,
                node.type.value,
                node. ip_address,
                f"[{status_style}]{node.status.value}[/{status_style}]",
                node.vendor,
            )

        console.print(table)

        # Print links table
        links_table = Table(title="Network Links")
        links_table.add_column("Source", style="cyan")
        links_table.add_column("Target", style="cyan")
        links_table.add_column("Bandwidth", style="green")
        links_table.add_column("Latency", style="yellow")

        for link in network_sim.topology.links:
            links_table.add_row(
                link. source_node_id,
                link. target_node_id,
                f"{link.bandwidth_mbps} Mbps",
                f"{link.latency_ms} ms",
            )

        console.print(links_table)


@cli.command()
@click. option("--count", default=100, help="Number of logs to generate")
@click.option("--time-range", default=60, help="Time range in minutes")
@click. option("--output", "-o", type=click.Path(), help="Output file (JSON)")
def generate_logs(count: int, time_range: int, output: Optional[str]):
    """Generate a batch of network logs."""
    network_sim, log_gen, _, _ = get_simulator_components()

    console.print(f"[bold]Generating {count} logs over {time_range} minutes.. .[/bold]")

    logs = log_gen. generate_batch(count=count, time_range_minutes=time_range)

    logs_data = [
        {
            "id": log.id,
            "timestamp": log.timestamp.isoformat(),
            "node_id": log. node_id,
            "node_name": log. node_name,
            "level": log.level. value,
            "source": log.source,
            "message": log.message,
            "metadata": log.metadata,
        }
        for log in logs
    ]

    if output:
        output_path = Path(output)
        output_path.parent. mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(logs_data, f, indent=2)
        console.print(f"[green]✓ Saved {len(logs)} logs to {output}[/green]")
    else:
        # Print to console
        table = Table(title=f"Generated Logs ({len(logs)} entries)")
        table. add_column("Timestamp", style="dim")
        table. add_column("Node", style="cyan")
        table. add_column("Level", style="yellow")
        table. add_column("Source", style="blue")
        table.add_column("Message", style="white", max_width=50)

        # Show last 20 logs
        for log in logs[-20:]:
            level_style = {
                "DEBUG": "dim",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red bold",
            }.get(log.level. value, "white")

            table.add_row(
                log.timestamp.strftime("%H:%M:%S"),
                log.node_name,
                f"[{level_style}]{log. level.value}[/{level_style}]",
                log.source,
                log.message[:50] + "..." if len(log.message) > 50 else log.message,
            )

        console.print(table)
        if len(logs) > 20:
            console.print(f"[dim](Showing last 20 of {len(logs)} logs)[/dim]")


@cli. command()
@click.option("--output", "-o", type=click.Path(), help="Output file (JSON)")
def generate_telemetry(output: Optional[str]):
    """Generate telemetry snapshots for all nodes."""
    network_sim, _, tel_gen, _ = get_simulator_components()

    console.print("[bold]Generating telemetry snapshots.. .[/bold]")

    snapshots = tel_gen.generate_all_snapshots()

    snapshots_data = [
        {
            "id": s.id,
            "timestamp": s. timestamp.isoformat(),
            "node_id": s. node_id,
            "node_name": s.node_name,
            "status": s.status. value,
            "metrics": [
                {
                    "type": m.metric_type.value,
                    "value": m.value,
                    "unit": m.unit,
                    "oid": m.oid,
                }
                for m in s.metrics
            ],
        }
        for s in snapshots
    ]

    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(snapshots_data, f, indent=2)
        console.print(f"[green]✓ Saved {len(snapshots)} snapshots to {output}[/green]")
    else:
        # Print to console
        table = Table(title="Telemetry Snapshots")
        table.add_column("Node", style="cyan")
        table.add_column("Status", style="yellow")
        table.add_column("CPU %", style="green")
        table.add_column("Memory %", style="green")
        table. add_column("Latency", style="blue")
        table.add_column("Packet Loss", style="red")

        for snapshot in snapshots:
            status_style = {
                NodeStatus. HEALTHY: "green",
                NodeStatus. WARNING: "yellow",
                NodeStatus. CRITICAL: "red",
            }.get(snapshot. status, "white")

            cpu = next((m. value for m in snapshot.metrics if m. metric_type. value == "cpu_utilization"), "-")
            memory = next((m.value for m in snapshot. metrics if m.metric_type.value == "memory_utilization"), "-")
            latency = next((m.value for m in snapshot.metrics if m.metric_type.value == "latency"), "-")
            packet_loss = next((m.value for m in snapshot. metrics if m.metric_type.value == "packet_loss"), "-")

            table.add_row(
                snapshot.node_name,
                f"[{status_style}]{snapshot.status.value}[/{status_style}]",
                f"{cpu}%" if cpu != "-" else "-",
                f"{memory}%" if memory != "-" else "-",
                f"{latency} ms" if latency != "-" else "-",
                f"{packet_loss}%" if packet_loss != "-" else "-",
            )

        console.print(table)


@cli.command()
@click.option("--node", required=True, help="Node ID to inject anomaly")
@click.option("--type", "anomaly_type", required=True,
              type=click.Choice([t.value for t in AnomalyType]),
              help="Type of anomaly")
@click.option("--severity", default="medium",
              type=click.Choice([s.value for s in AnomalySeverity]),
              help="Severity level")
@click.option("--show-logs", is_flag=True, help="Show generated logs")
def inject_anomaly(node: str, anomaly_type: str, severity: str, show_logs: bool):
    """Inject an anomaly on a specific node."""
    network_sim, log_gen, tel_gen, injector = get_simulator_components()

    anomaly = injector.inject_anomaly(
        node,
        AnomalyType(anomaly_type),
        AnomalySeverity(severity),
    )

    if anomaly is None:
        console.print(f"[red]✗ Failed to inject anomaly.  Node '{node}' not found.[/red]")
        return

    console.print(Panel(
        f"[bold]Anomaly ID:[/bold] {anomaly.id}\n"
        f"[bold]Type:[/bold] {anomaly.anomaly_type.value}\n"
        f"[bold]Severity:[/bold] {anomaly. severity.value}\n"
        f"[bold]Node:[/bold] {anomaly.node_id}\n"
        f"[bold]Description:[/bold] {anomaly.description}",
        title="[green]✓ Anomaly Injected[/green]",
        border_style="green"
    ))

    if show_logs:
        logs = injector.generate_anomaly_logs(anomaly)
        console.print("\n[bold]Generated Logs:[/bold]")
        for log in logs:
            level_style = {
                "DEBUG": "dim",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red bold",
            }.get(log.level. value, "white")
            console.print(f"  [{level_style}]{log.level.value}[/{level_style}] {log.message}")

    # Show affected metrics
    console.print("\n[bold]Current Telemetry:[/bold]")
    node_obj = network_sim. get_node(node)
    if node_obj:
        snapshot = tel_gen.generate_snapshot(node_obj)
        for metric in snapshot.metrics:
            if metric.metadata.get("anomaly_override"):
                console.print(f"  [red]⚠ {metric.metric_type.value}: {metric.value} {metric.unit}[/red]")
            else:
                console.print(f"  {metric.metric_type.value}: {metric.value} {metric.unit}")


@cli.command()
@click.option("--scenario", required=True, help="Scenario name")
def inject_scenario(scenario: str):
    """Inject a pre-defined incident scenario."""
    network_sim, log_gen, tel_gen, injector = get_simulator_components()

    available = injector.get_available_scenarios()

    if scenario not in available:
        console.print(f"[red]✗ Unknown scenario: {scenario}[/red]")
        console.print("\n[bold]Available scenarios:[/bold]")
        for name, desc in available. items():
            console.print(f"  • [cyan]{name}[/cyan]: {desc}")
        return

    anomalies = injector. create_incident_scenario(scenario)

    console.print(Panel(
        f"[bold]Scenario:[/bold] {scenario}\n"
        f"[bold]Description:[/bold] {available[scenario]}\n"
        f"[bold]Anomalies Created:[/bold] {len(anomalies)}",
        title="[green]✓ Scenario Injected[/green]",
        border_style="green"
    ))

    if anomalies:
        table = Table(title="Injected Anomalies")
        table.add_column("ID", style="cyan")
        table.add_column("Node", style="green")
        table. add_column("Type", style="yellow")
        table.add_column("Severity", style="red")

        for anomaly in anomalies:
            table.add_row(
                anomaly.id,
                anomaly.node_id,
                anomaly.anomaly_type.value,
                anomaly. severity.value,
            )

        console.print(table)


@cli.command()
def list_scenarios():
    """List available incident scenarios."""
    _, _, _, injector = get_simulator_components()

    scenarios = injector.get_available_scenarios()

    console.print(Panel("[bold]Available Incident Scenarios[/bold]", border_style="blue"))

    for name, description in scenarios.items():
        console.print(f"\n  [cyan bold]{name}[/cyan bold]")
        console. print(f"  {description}")


@cli.command()
@click.option("--interval", default=5, help="Interval between generations in seconds")
@click.option("--duration", default=60, help="Total duration in seconds (0 = infinite)")
@click.option("--output-dir", type=click.Path(), default="./output", help="Output directory")
@click.option("--inject-anomalies", is_flag=True, help="Randomly inject anomalies")
def run(interval: int, duration: int, output_dir: str, inject_anomalies: bool):
    """Run continuous simulation."""
    network_sim, log_gen, tel_gen, injector = get_simulator_components()

    output_path = Path(output_dir)
    output_path. mkdir(parents=True, exist_ok=True)

    logs_file = output_path / "logs.jsonl"
    telemetry_file = output_path / "telemetry.jsonl"

    console.print(Panel(
        f"[bold]Interval:[/bold] {interval}s\n"
        f"[bold]Duration:[/bold] {'Infinite' if duration == 0 else f'{duration}s'}\n"
        f"[bold]Output:[/bold] {output_path}\n"
        f"[bold]Inject Anomalies:[/bold] {'Yes' if inject_anomalies else 'No'}",
        title="[bold blue]Starting Continuous Simulation[/bold blue]",
        border_style="blue"
    ))

    start_time = time. time()
    iteration = 0

    try:
        while True:
            iteration += 1
            elapsed = time.time() - start_time

            if duration > 0 and elapsed >= duration:
                break

            # Generate logs
            logs = log_gen. generate_batch(count=10, time_range_minutes=1)

            # Generate telemetry
            snapshots = tel_gen.generate_all_snapshots()

            # Maybe inject anomaly
            if inject_anomalies and random.random() < 0.1:  # 10% chance
                anomaly = injector.inject_random_anomaly()
                if anomaly:
                    console.print(f"[yellow]⚠ Injected anomaly: {anomaly.anomaly_type.value} on {anomaly.node_id}[/yellow]")
                    # Generate anomaly logs
                    anomaly_logs = injector.generate_anomaly_logs(anomaly)
                    logs.extend(anomaly_logs)

            # Write to files
            with open(logs_file, "a") as f:
                for log in logs:
                    f.write(json.dumps({
                        "timestamp": log.timestamp. isoformat(),
                        "node_id": log. node_id,
                        "level": log.level. value,
                        "source": log.source,
                        "message": log.message,
                    }) + "\n")

            with open(telemetry_file, "a") as f:
                for snapshot in snapshots:
                    f.write(json.dumps({
                        "timestamp": snapshot.timestamp.isoformat(),
                        "node_id": snapshot.node_id,
                        "status": snapshot.status. value,
                        "metrics": {
                            m.metric_type. value: m.value
                            for m in snapshot.metrics
                        },
                    }) + "\n")

            # Print status
            active_anomalies = len(injector.get_active_anomalies())
            console.print(
                f"[dim][{datetime.now().strftime('%H:%M:%S')}][/dim] "
                f"Iteration {iteration}: "
                f"{len(logs)} logs, "
                f"{len(snapshots)} snapshots"
                f"{f', {active_anomalies} active anomalies' if active_anomalies else ''}"
            )

            time.sleep(interval)

    except KeyboardInterrupt:
        console.print("\n[yellow]Simulation stopped by user[/yellow]")

    console.print(f"\n[green]✓ Simulation complete.  Output saved to {output_path}[/green]")


@cli.command()
def clear_anomalies():
    """Clear all active anomalies."""
    _, _, _, injector = get_simulator_components()

    count = injector.clear_all_anomalies()
    console.print(f"[green]✓ Cleared {count} anomalies[/green]")


if __name__ == "__main__":
    cli()