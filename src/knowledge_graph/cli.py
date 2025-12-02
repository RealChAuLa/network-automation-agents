"""
CLI for Knowledge Graph operations. 
"""

import json
from pathlib import Path

import click
from rich. console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree

from src.knowledge_graph.client import Neo4jClient
from src.knowledge_graph.topology import TopologyManager
from src. knowledge_graph.policies import PolicyManager
from src.simulator.network_sim import NetworkSimulator
from src. models.network import NodeStatus
from src. models.policy import PolicyStatus


console = Console()


def get_client() -> Neo4jClient:
    """Get Neo4j client."""
    client = Neo4jClient()
    try:
        client.connect()
        return client
    except Exception as e:
        console.print(f"[red]✗ Failed to connect to Neo4j: {e}[/red]")
        console.print("[dim]Make sure Neo4j is running and credentials are correct.[/dim]")
        raise click.Abort()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Knowledge Graph CLI
    
    Manage network topology and policies in Neo4j. 
    """
    pass


# =============================================================================
# Connection Commands
# =============================================================================

@cli.command()
def status():
    """Check Neo4j connection status."""
    client = Neo4jClient()
    
    try:
        client.connect()
        stats = client.get_database_stats()
        
        console.print(Panel(
            f"[bold green]✓ Connected to Neo4j[/bold green]\n\n"
            f"[bold]Database:[/bold] {stats['database']}\n"
            f"[bold]Nodes:[/bold] {stats['node_count']}\n"
            f"[bold]Relationships:[/bold] {stats['relationship_count']}",
            title="Neo4j Status",
            border_style="green"
        ))
    except Exception as e:
        console.print(Panel(
            f"[bold red]✗ Connection Failed[/bold red]\n\n"
            f"[bold]Error:[/bold] {str(e)}\n\n"
            f"[dim]Make sure Neo4j is running:[/dim]\n"
            f"  docker run -d --name neo4j \\\n"
            f"    -p 7474:7474 -p 7687:7687 \\\n"
            f"    -e NEO4J_AUTH=neo4j/password \\\n"
            f"    neo4j:latest",
            title="Neo4j Status",
            border_style="red"
        ))
    finally:
        client. close()


@cli.command()
def init():
    """Initialize database with indexes."""
    client = get_client()
    
    try:
        console.print("[bold]Creating indexes...[/bold]")
        client. create_indexes()
        console. print("[green]✓ Indexes created successfully[/green]")
    finally:
        client. close()


@cli.command()
@click.confirmation_option(prompt="Are you sure you want to clear all data?")
def clear():
    """Clear all data from the database."""
    client = get_client()
    
    try:
        client.clear_database()
        console.print("[green]✓ Database cleared[/green]")
    finally:
        client.close()


# =============================================================================
# Topology Commands
# =============================================================================

@cli.group()
def topology():
    """Manage network topology."""
    pass


@topology.command("import")
def import_topology():
    """Import topology from simulator into Neo4j."""
    client = get_client()
    
    try:
        # Create simulator topology
        console.print("[bold]Creating network topology...[/bold]")
        sim = NetworkSimulator()
        sim.create_default_topology()
        
        # Import into Neo4j
        console.print("[bold]Importing into Neo4j...[/bold]")
        topo_mgr = TopologyManager(client)
        result = topo_mgr.import_from_simulator(sim)
        
        console.print(Panel(
            f"[green]✓ Import complete[/green]\n\n"
            f"[bold]Nodes imported:[/bold] {result['nodes']}\n"
            f"[bold]Links imported:[/bold] {result['links']}",
            title="Topology Import",
            border_style="green"
        ))
    finally:
        client. close()


@topology.command("show")
@click.option("--format", "output_format", type=click.Choice(["table", "json", "tree"]), default="table")
def show_topology(output_format: str):
    """Display network topology."""
    client = get_client()
    
    try:
        topo_mgr = TopologyManager(client)
        nodes = topo_mgr.get_all_nodes()
        links = topo_mgr.get_all_links()
        
        if output_format == "json":
            data = {
                "nodes": [{"id": n.id, "name": n.name, "type": n. type. value, "status": n. status.value} for n in nodes],
                "links": [{"source": l. source_node_id, "target": l.target_node_id} for l in links],
            }
            console.print_json(json.dumps(data, indent=2))
        
        elif output_format == "tree":
            tree = Tree("[bold]Network Topology[/bold]")
            
            # Group nodes by type
            by_type = {}
            for node in nodes:
                type_name = node. type.value
                if type_name not in by_type:
                    by_type[type_name] = []
                by_type[type_name].append(node)
            
            for type_name, type_nodes in sorted(by_type. items()):
                type_branch = tree.add(f"[cyan]{type_name}[/cyan] ({len(type_nodes)})")
                for node in type_nodes:
                    status_color = {
                        "healthy": "green",
                        "warning": "yellow",
                        "critical": "red",
                        "down": "red bold",
                    }. get(node.status.value, "white")
                    type_branch.add(f"{node.name} [{status_color}]{node.status.value}[/{status_color}]")
            
            console.print(tree)
        
        else:  # table
            summary = topo_mgr.get_topology_summary()
            console.print(Panel(
                f"[bold]Total Nodes:[/bold] {summary['nodes']}\n"
                f"[bold]Total Links:[/bold] {summary['links']}\n"
                f"[bold]Node Types:[/bold] {', '.join(summary['types'])}\n"
                f"[bold]Locations:[/bold] {', '.join(summary['locations'])}",
                title="Topology Summary"
            ))
            
            table = Table(title="Network Nodes")
            table. add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            table. add_column("Type", style="yellow")
            table.add_column("IP Address", style="blue")
            table.add_column("Status", style="magenta")
            table.add_column("Vendor")
            
            for node in nodes:
                status_style = {
                    NodeStatus.HEALTHY: "green",
                    NodeStatus.WARNING: "yellow",
                    NodeStatus. CRITICAL: "red",
                    NodeStatus.DOWN: "red bold",
                }.get(node. status, "white")
                
                table.add_row(
                    node.id,
                    node.name,
                    node. type.value,
                    node.ip_address,
                    f"[{status_style}]{node. status.value}[/{status_style}]",
                    node.vendor,
                )
            
            console.print(table)
    finally:
        client.close()


@topology.command("node")
@click. argument("node_id")
def show_node(node_id: str):
    """Show details for a specific node."""
    client = get_client()
    
    try:
        topo_mgr = TopologyManager(client)
        node = topo_mgr.get_node(node_id)
        
        if not node:
            console.print(f"[red]✗ Node not found: {node_id}[/red]")
            return
        
        # Get connected nodes
        connected = topo_mgr.get_connected_nodes(node_id)
        
        console.print(Panel(
            f"[bold]ID:[/bold] {node.id}\n"
            f"[bold]Name:[/bold] {node.name}\n"
            f"[bold]Type:[/bold] {node. type.value}\n"
            f"[bold]IP Address:[/bold] {node.ip_address}\n"
            f"[bold]Status:[/bold] {node.status. value}\n"
            f"[bold]Location:[/bold] {node.location}\n"
            f"[bold]Vendor:[/bold] {node.vendor}\n"
            f"[bold]Model:[/bold] {node.model}\n"
            f"[bold]Interfaces:[/bold] {', '.join(node. interfaces[:5])}{'...' if len(node.interfaces) > 5 else ''}",
            title=f"Node: {node.name}",
            border_style="cyan"
        ))
        
        if connected:
            table = Table(title="Connected Nodes")
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Type", style="yellow")
            
            for conn in connected:
                table. add_row(conn.id, conn. name, conn.type.value)
            
            console.print(table)
    finally:
        client.close()


@topology.command("path")
@click. argument("source_id")
@click. argument("target_id")
def find_path(source_id: str, target_id: str):
    """Find path between two nodes."""
    client = get_client()
    
    try:
        topo_mgr = TopologyManager(client)
        path = topo_mgr.find_path(source_id, target_id)
        
        if not path:
            console.print(f"[yellow]No path found between {source_id} and {target_id}[/yellow]")
            return
        
        console. print(f"\n[bold]Path ({len(path)} hops):[/bold]\n")
        
        for i, node in enumerate(path):
            prefix = "  " if i == 0 else "  │\n  ▼\n  "
            console. print(f"{prefix}[cyan]{node.name}[/cyan] ({node.type. value})")
        
        console.print()
    finally:
        client.close()


@topology.command("critical")
def show_critical_nodes():
    """Show critical nodes in the network."""
    client = get_client()
    
    try:
        topo_mgr = TopologyManager(client)
        critical = topo_mgr.get_critical_nodes()
        
        if not critical:
            console.print("[yellow]No critical nodes found[/yellow]")
            return
        
        table = Table(title="Critical Nodes")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Type", style="yellow")
        table. add_column("Status", style="magenta")
        
        for node in critical:
            status_style = "green" if node.status == NodeStatus.HEALTHY else "red"
            table. add_row(
                node.id,
                node.name,
                node. type.value,
                f"[{status_style}]{node.status.value}[/{status_style}]",
            )
        
        console.print(table)
    finally:
        client. close()


# =============================================================================
# Policy Commands
# =============================================================================

@cli.group()
def policies():
    """Manage policies."""
    pass


@policies.command("load")
@click. argument("file_path", type=click.Path(exists=True))
def load_policies(file_path: str):
    """Load policies from a YAML file."""
    client = get_client()
    
    try:
        policy_mgr = PolicyManager(client)
        count = policy_mgr.load_policies_from_yaml(file_path)
        
        console.print(f"[green]✓ Loaded {count} policies from {file_path}[/green]")
    except Exception as e:
        console.print(f"[red]✗ Failed to load policies: {e}[/red]")
    finally:
        client.close()


@policies. command("list")
@click.option("--status", type=click.Choice(["active", "inactive", "draft"]), default=None)
def list_policies(status: str):
    """List all policies."""
    client = get_client()
    
    try:
        policy_mgr = PolicyManager(client)
        
        if status:
            policy_list = policy_mgr.get_all_policies(PolicyStatus(status))
        else:
            policy_list = policy_mgr.get_all_policies()
        
        if not policy_list:
            console.print("[yellow]No policies found[/yellow]")
            return
        
        table = Table(title=f"Policies ({len(policy_list)} total)")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table. add_column("Type", style="yellow")
        table.add_column("Priority", style="blue")
        table. add_column("Status", style="magenta")
        table.add_column("Conditions", style="white")
        
        for policy in policy_list:
            status_style = "green" if policy.status == PolicyStatus. ACTIVE else "dim"
            table. add_row(
                policy.id,
                policy.name,
                policy. policy_type.value,
                str(policy.priority),
                f"[{status_style}]{policy.status. value}[/{status_style}]",
                str(len(policy.conditions)),
            )
        
        console.print(table)
    finally:
        client.close()


@policies.command("show")
@click. argument("policy_id")
def show_policy(policy_id: str):
    """Show details for a specific policy."""
    client = get_client()
    
    try:
        policy_mgr = PolicyManager(client)
        policy = policy_mgr.get_policy(policy_id)
        
        if not policy:
            console.print(f"[red]✗ Policy not found: {policy_id}[/red]")
            return
        
        # Build conditions string
        conditions_str = "\n".join([
            f"  • {c.field} {c.operator. value} {c. value}"
            for c in policy.conditions
        ]) or "  (none)"
        
        # Build actions string
        actions_str = "\n". join([
            f"  • {a.action_type.value}" + (f" → {a.target}" if a.target else "")
            for a in policy.actions
        ]) or "  (none)"
        
        console.print(Panel(
            f"[bold]ID:[/bold] {policy.id}\n"
            f"[bold]Name:[/bold] {policy.name}\n"
            f"[bold]Description:[/bold] {policy.description or '(none)'}\n"
            f"[bold]Type:[/bold] {policy.policy_type.value}\n"
            f"[bold]Status:[/bold] {policy.status.value}\n"
            f"[bold]Priority:[/bold] {policy.priority}\n"
            f"[bold]Version:[/bold] {policy.version}\n\n"
            f"[bold]Conditions:[/bold]\n{conditions_str}\n\n"
            f"[bold]Actions:[/bold]\n{actions_str}\n\n"
            f"[bold]Applies to Node Types:[/bold] {', '.join(policy.applies_to_node_types) or 'All'}\n"
            f"[bold]Tags:[/bold] {', '.join(policy.tags) or '(none)'}",
            title=f"Policy: {policy.name}",
            border_style="cyan"
        ))
    finally:
        client. close()


@policies.command("evaluate")
@click. option("--anomaly-type", required=True, help="Anomaly type (e.g., HIGH_CPU)")
@click.option("--severity", default="medium", help="Severity level")
@click.option("--node-type", default=None, help="Node type filter")
@click. option("--cpu", type=float, default=None, help="CPU utilization value")
@click. option("--memory", type=float, default=None, help="Memory utilization value")
def evaluate_policies(anomaly_type: str, severity: str, node_type: str, cpu: float, memory: float):
    """Evaluate policies against a context."""
    client = get_client()
    
    try:
        policy_mgr = PolicyManager(client)
        
        # Build context
        context = {
            "anomaly_type": anomaly_type,
            "severity": severity,
        }
        if cpu is not None:
            context["cpu_utilization"] = cpu
        if memory is not None:
            context["memory_utilization"] = memory
        if node_type:
            context["node_type"] = node_type
        
        console.print(f"[bold]Evaluating policies with context:[/bold]")
        console. print_json(json.dumps(context, indent=2))
        console.print()
        
        results = policy_mgr.evaluate_policies(context, node_type)
        
        if not results:
            console. print("[yellow]No policies to evaluate[/yellow]")
            return
        
        # Show matching policies
        matched = [r for r in results if r.matched]
        not_matched = [r for r in results if not r.matched]
        
        if matched:
            console.print(f"[green bold]✓ {len(matched)} policies matched:[/green bold]\n")
            
            for result in matched:
                actions_str = ", ".join([a.action_type. value for a in result.recommended_actions])
                console.print(f"  [green]• {result.policy_name}[/green] (ID: {result.policy_id})")
                console.print(f"    Actions: [cyan]{actions_str}[/cyan]")
                console.print()
        else:
            console. print("[yellow]No policies matched[/yellow]\n")
        
        if not_matched and click.confirm("Show non-matching policies?", default=False):
            console.print(f"\n[dim]{len(not_matched)} policies did not match:[/dim]\n")
            for result in not_matched[:5]:
                console.print(f"  [dim]• {result. policy_name}[/dim]")
                if result.conditions_not_met:
                    console.print(f"    [dim]Missing: {result.conditions_not_met[0]}[/dim]")
    finally:
        client.close()


@policies.command("seed")
def seed_default_policies():
    """Seed database with default policies."""
    client = get_client()
    
    try:
        policy_mgr = PolicyManager(client)
        
        # Check if policies directory exists
        policies_dir = Path("policies")
        if not policies_dir. exists():
            policies_dir.mkdir(parents=True)
            console.print(f"[dim]Created policies directory: {policies_dir}[/dim]")
        
        # Create default policy file if it doesn't exist
        default_file = policies_dir / "network_policies.yaml"
        if not default_file.exists():
            console.print("[yellow]No policy files found.  Creating default policies.. .[/yellow]")
            _create_default_policy_file(default_file)
        
        # Load all YAML files in policies directory
        total_loaded = 0
        for yaml_file in policies_dir.glob("*. yaml"):
            try:
                count = policy_mgr.load_policies_from_yaml(str(yaml_file))
                console.print(f"[green]✓ Loaded {count} policies from {yaml_file. name}[/green]")
                total_loaded += count
            except Exception as e:
                console. print(f"[red]✗ Failed to load {yaml_file.name}: {e}[/red]")
        
        console. print(f"\n[bold green]✓ Total policies loaded: {total_loaded}[/bold green]")
    finally:
        client.close()


def _create_default_policy_file(file_path: Path):
    """Create default policy YAML file."""
    default_policies = '''# Network Automation Policies
# These policies define automated responses to network anomalies

policies:
  # =============================================================================
  # HIGH CPU Policies
  # =============================================================================
  
  - id: POL-CPU-001
    name: High CPU - Restart Service
    description: Restart affected service when CPU is critically high
    policy_type: remediation
    status: active
    priority: 10
    conditions:
      - field: anomaly_type
        operator: equals
        value: HIGH_CPU
      - field: severity
        operator: in
        value: ["critical", "high"]
      - field: cpu_utilization
        operator: greater_than
        value: 90
    actions:
      - action_type: restart_service
        target: affected_service
        parameters:
          graceful: true
          timeout: 30
        timeout_seconds: 120
        retry_count: 1
    applies_to_node_types:
      - router_core
      - router_edge
      - switch_distribution
    tags:
      - cpu
      - auto-remediation

  - id: POL-CPU-002
    name: High CPU - Log and Monitor
    description: Log warning for moderate CPU usage
    policy_type: remediation
    status: active
    priority: 50
    conditions:
      - field: anomaly_type
        operator: equals
        value: HIGH_CPU
      - field: severity
        operator: equals
        value: medium
    actions:
      - action_type: log_only
        parameters:
          level: warning
          message: "Elevated CPU detected, monitoring"
    tags:
      - cpu
      - monitoring

  # =============================================================================
  # Memory Policies
  # =============================================================================
  
  - id: POL-MEM-001
    name: Memory Leak - Clear Cache and Restart
    description: Clear cache and restart service for memory leak
    policy_type: remediation
    status: active
    priority: 20
    conditions:
      - field: anomaly_type
        operator: equals
        value: MEMORY_LEAK
      - field: severity
        operator: in
        value: ["critical", "high"]
    actions:
      - action_type: clear_cache
        parameters:
          scope: all
      - action_type: restart_service
        target: affected_service
        parameters:
          graceful: true
    applies_to_node_types:
      - server
      - router_core
    tags:
      - memory
      - auto-remediation

  # =============================================================================
  # Interface Policies
  # =============================================================================
  
  - id: POL-INT-001
    name: Interface Down - Failover
    description: Trigger failover when interface goes down
    policy_type: remediation
    status: active
    priority: 5
    conditions:
      - field: anomaly_type
        operator: equals
        value: INTERFACE_DOWN
      - field: severity
        operator: equals
        value: critical
    actions:
      - action_type: failover
        parameters:
          mode: automatic
          verify_backup: true
      - action_type: notify
        parameters:
          channel: ops-alerts
          priority: high
    applies_to_node_types:
      - router_core
      - switch_distribution
    tags:
      - interface
      - failover
      - critical

  # =============================================================================
  # Latency Policies
  # =============================================================================
  
  - id: POL-LAT-001
    name: High Latency - Rate Limit
    description: Apply rate limiting when latency is high
    policy_type: remediation
    status: active
    priority: 30
    conditions:
      - field: anomaly_type
        operator: equals
        value: HIGH_LATENCY
      - field: severity
        operator: in
        value: ["critical", "high"]
    actions:
      - action_type: rate_limit
        parameters:
          reduction_percent: 20
          duration_minutes: 15
    tags:
      - latency
      - traffic-management

  # =============================================================================
  # Security Policies
  # =============================================================================
  
  - id: POL-SEC-001
    name: Auth Failure - Block and Alert
    description: Block IP and alert on authentication failures
    policy_type: remediation
    status: active
    priority: 1
    conditions:
      - field: anomaly_type
        operator: equals
        value: AUTH_FAILURE
      - field: severity
        operator: in
        value: ["critical", "high"]
    actions:
      - action_type: block_traffic
        parameters:
          duration_minutes: 60
          source: offending_ip
      - action_type: notify
        parameters:
          channel: security-alerts
          priority: critical
      - action_type: escalate
        parameters:
          team: security
    tags:
      - security
      - authentication
      - critical

  # =============================================================================
  # Escalation Policies
  # =============================================================================
  
  - id: POL-ESC-001
    name: Service Degradation - Escalate
    description: Escalate to operations team for service degradation
    policy_type: escalation
    status: active
    priority: 15
    conditions:
      - field: anomaly_type
        operator: equals
        value: SERVICE_DEGRADATION
      - field: severity
        operator: equals
        value: critical
    actions:
      - action_type: notify
        parameters:
          channel: ops-critical
          priority: critical
      - action_type: escalate
        parameters:
          team: operations
          sla_minutes: 15
    tags:
      - escalation
      - service-degradation

# =============================================================================
# Compliance Rules
# =============================================================================

compliance_rules:
  - id: COMP-001
    name: Maintenance Window Required
    description: Major changes require maintenance window
    regulation: INTERNAL
    severity: high
    check_type: maintenance_window
    parameters:
      required_for:
        - restart_node
        - failover
        - update_config
      window_hours:
        start: 2
        end: 6
      timezone: UTC
    enforcement: block
    tags:
      - maintenance
      - change-control

  - id: COMP-002
    name: Change Approval Required
    description: Configuration changes require approval
    regulation: SOC2
    severity: high
    check_type: approval_required
    parameters:
      required_for:
        - update_config
      approvers:
        - network-admins
        - change-board
    enforcement: block
    tags:
      - soc2
      - change-control

  - id: COMP-003
    name: Audit Trail Required
    description: All actions must be logged to audit trail
    regulation: SOC2
    severity: medium
    check_type: audit_logging
    parameters:
      log_fields:
        - timestamp
        - action
        - actor
        - target
        - result
    enforcement: warn
    tags:
      - soc2
      - audit
'''
    
    with open(file_path, "w") as f:
        f.write(default_policies)
    
    console.print(f"[green]✓ Created default policy file: {file_path}[/green]")


# =============================================================================
# Combined Commands
# =============================================================================

@cli.command("setup")
def setup_all():
    """Setup everything: init, import topology, seed policies."""
    client = get_client()
    
    try:
        console.print("[bold]Setting up Knowledge Graph...[/bold]\n")
        
        # Create indexes
        console.print("1. Creating indexes...")
        client.create_indexes()
        console.print("[green]   ✓ Indexes created[/green]\n")
        
        # Import topology
        console.print("2. Importing network topology...")
        sim = NetworkSimulator()
        sim. create_default_topology()
        topo_mgr = TopologyManager(client)
        result = topo_mgr.import_from_simulator(sim)
        console.print(f"[green]   ✓ Imported {result['nodes']} nodes and {result['links']} links[/green]\n")
        
        # Seed policies
        console. print("3.  Seeding policies...")
        policy_mgr = PolicyManager(client)
        policies_dir = Path("policies")
        policies_dir.mkdir(exist_ok=True)
        
        default_file = policies_dir / "network_policies.yaml"
        if not default_file.exists():
            _create_default_policy_file(default_file)
        
        count = policy_mgr.load_policies_from_yaml(str(default_file))
        console.print(f"[green]   ✓ Loaded {count} policies[/green]\n")
        
        # Summary
        stats = client.get_database_stats()
        console.print(Panel(
            f"[bold green]✓ Setup Complete![/bold green]\n\n"
            f"[bold]Database Stats:[/bold]\n"
            f"  • Nodes: {stats['node_count']}\n"
            f"  • Relationships: {stats['relationship_count']}\n\n"
            f"[bold]Next Steps:[/bold]\n"
            f"  • View topology: [cyan]knowledge-graph topology show[/cyan]\n"
            f"  • View policies: [cyan]knowledge-graph policies list[/cyan]\n"
            f"  • Evaluate policies: [cyan]knowledge-graph policies evaluate --anomaly-type HIGH_CPU --severity critical[/cyan]",
            title="Knowledge Graph Setup",
            border_style="green"
        ))
    finally:
        client.close()


if __name__ == "__main__":
    cli()