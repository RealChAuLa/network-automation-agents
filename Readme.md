# 🌐 Network Automation Agents

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License:  MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-purple.svg)](https://modelcontextprotocol.io/)

**Blockchain-secured MCP Registry for Telco Network Automation with AI Agents**

A comprehensive, production-ready framework for autonomous network monitoring, diagnosis, policy enforcement, and remediation using AI agents powered by LangGraph and the Model Context Protocol (MCP).

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Key Features](#-key-features)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [Components](#-components)
  - [Network Simulator](#network-simulator)
  - [Knowledge Graph (Neo4j)](#knowledge-graph-neo4j)
  - [MCP Server](#mcp-server)
  - [AI Agents](#ai-agents)
  - [Orchestrator Pipeline](#orchestrator-pipeline)
  - [Audit System (immudb)](#audit-system-immudb)
- [CLI Commands](#-cli-commands)
- [API Reference](#-api-reference)
- [Development](#-development)
- [Testing](#-testing)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 Overview

Network Automation Agents is an intelligent, autonomous network operations platform designed for telecommunications and enterprise networks. It combines: 

- **AI-Powered Agents**: Four specialized agents (Discovery, Policy, Compliance, Execution) work together to detect issues, evaluate policies, ensure compliance, and execute remediation actions.
- **LangGraph Orchestration**: A state-machine-based pipeline that coordinates agent workflows with conditional routing and state management.
- **Model Context Protocol (MCP)**: Standardized tool interface allowing AI agents to interact with network infrastructure through well-defined tools.
- **Knowledge Graph (Neo4j)**: Network topology, policies, and relationships stored in a graph database for intelligent querying and impact analysis. 
- **Immutable Audit Trail (immudb)**: All agent intents, actions, and results are cryptographically secured in an immutable database for compliance and forensics.

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          NETWORK AUTOMATION AGENTS                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  DISCOVERY  │───▶│   POLICY    │───▶│ COMPLIANCE  │───▶│  EXECUTION  │  │
│  │    AGENT    │    │    AGENT    │    │    AGENT    │    │    AGENT    │  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │
│         │                  │                  │                  │         │
│         └──────────────────┴──────────────────┴──────────────────┘         │
│                                    │                                        │
│                          ┌─────────▼─────────┐                             │
│                          │    MCP SERVER     │                             │
│                          │  (Tool Registry)  │                             │
│                          └─────────┬─────────┘                             │
│                                    │                                        │
│         ┌──────────────────────────┼──────────────────────────┐            │
│         │                          │                          │            │
│  ┌──────▼──────┐           ┌───────▼───────┐          ┌──────▼──────┐     │
│  │   NEO4J     │           │   SIMULATOR   │          │   IMMUDB    │     │
│  │ (Knowledge  │           │   (Network    │          │   (Audit    │     │
│  │   Graph)    │           │   Topology)   │          │    Trail)   │     │
│  └─────────────┘           └───────────────┘          └─────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pipeline Flow

```
┌─────────────┐
│  DISCOVERY  │ ─── Detects network issues using MCP tools + LLM analysis
└──────┬──────┘
       │
       ▼
 ◇ has issues? 
 │         │
 No        Yes
 │         │
 ▼         ▼
END   ┌─────────┐
      │ POLICY  │ ─── Evaluates policies and recommends actions
      └────┬────┘
           │
           ▼
      ◇ has actions?
      │         │
      No        Yes
      │         │
      ▼         ▼
     END  ┌───────────┐
          │COMPLIANCE │ ─── Validates actions against compliance rules
          └─────┬─────┘
                │
                ▼
           ◇ approved?
           │         │
           No        Yes
           │         │
           ▼         ▼
          END  ┌───────────┐
               │ EXECUTION │ ─── Executes approved remediation actions
               └─────┬─────┘
                     │
                     ▼
                    END
```

---

## ✨ Key Features

### 🔍 Intelligent Discovery
- Real-time network monitoring via telemetry and logs
- LLM-powered anomaly detection (supports Gemini, OpenAI, Claude)
- Automatic issue classification and severity assessment
- Support for both LLM-based and rule-based analysis

### 📋 Policy Management
- YAML-based policy definitions
- Condition-based rule evaluation with flexible operators
- Action recommendations based on policy matching
- Support for remediation, escalation, prevention, and compliance policies

### ✅ Compliance Enforcement
- Pre-execution compliance validation
- Maintenance window awareness
- Critical node protection
- Human approval requirements for high-risk actions
- Detailed denial logging for audit

### 🚀 Automated Execution
- Safe execution of remediation actions
- Verification of action outcomes
- Dry-run mode for testing
- Rollback capabilities
- Retry logic with configurable attempts

### 📊 Comprehensive Audit Trail
- Immutable audit logging with immudb
- Intent, Result, and Denial record types
- Cryptographic verification
- Full traceability from detection to resolution

---

## 📋 Prerequisites

- **Python**:  3.11 or higher
- **Neo4j**: 5.x (for knowledge graph)
- **immudb**:  1.5+ (for audit trail)
- **Docker**: (optional) for containerized deployment

### API Keys (for LLM features)
- Google Gemini API key (recommended)
- Or OpenAI / Anthropic API key

---

## 🚀 Installation

### Using pip (recommended)

```bash
# Clone the repository
git clone https://github.com/RealChAuLa/network-automation-agents. git
cd network-automation-agents

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### Using Docker

```bash
# Build and run with Docker Compose
docker-compose up -d
```

---

## ⚙ Configuration

### Environment Variables

Copy the example environment file and configure:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Simulator Configuration
SIMULATOR_OUTPUT_DIR=./output
SIMULATOR_DEFAULT_INTERVAL=5
SIMULATOR_DEFAULT_NODE_COUNT=10

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j

# MCP Server Configuration
MCP_SERVER_NAME=network-automation-mcp
MCP_SERVER_VERSION=0.1.0
MCP_LOG_LEVEL=INFO

# LLM Configuration
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-2. 0-flash

# Agent Configuration
AGENT_LOG_LEVEL=INFO
DISCOVERY_AGENT_INTERVAL_MINUTES=5
DISCOVERY_AGENT_ENABLED=true

# Audit Configuration (immudb)
AUDIT_ENABLED=true
IMMUDB_HOST=localhost
IMMUDB_PORT=3322
IMMUDB_USER=immudb
IMMUDB_PASSWORD=immudb
IMMUDB_DATABASE=defaultdb

# Orchestrator Configuration
ORCHESTRATOR_INTERVAL=5
PIPELINE_USE_LLM=true
PIPELINE_VERIFY=true
PIPELINE_DRY_RUN=false
```

---

## 🏃 Quick Start

### 1. Start Infrastructure Services

```bash
# Start Neo4j
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5

# Start immudb
docker run -d --name immudb \
  -p 3322:3322 \
  codenotary/immudb:latest
```

### 2. Initialize the Network Simulation

```bash
# Create and populate the simulated network
network-sim run --nodes 10

# Import topology to knowledge graph
knowledge-graph import
```

### 3. Start the MCP Server

```bash
mcp-server
```

### 4. Run the Discovery Agent

```bash
# Run with LLM analysis
discovery-agent run

# Run without LLM (rule-based only)
discovery-agent run --no-llm

# Run on a specific node
discovery-agent run --node router_core_01
```

### 5. Run the Full Pipeline

```bash
# Using the orchestrator CLI
python -m src.orchestrator.cli run

# With options
python -m src.orchestrator.cli run --dry-run --use-llm
```

---

## 📁 Project Structure

```
network-automation-agents/
├── docker/                    # Docker configuration files
├── policies/                  # Policy YAML definitions
├── src/
│   ├── agents/               # AI Agent implementations
│   │   ├── base. py          # Base agent class
│   │   ├── config.py        # Agent configuration
│   │   ├── compliance/      # Compliance Agent
│   │   │   ├── agent.py     # Main agent logic
│   │   │   ├── checks.py    # Compliance check implementations
│   │   │   ├── models.py    # Data models
│   │   │   ├── prompts.py   # LLM prompts
│   │   │   └── runner.py    # CLI runner
│   │   ├── discovery/       # Discovery Agent
│   │   │   ├── agent.py     # Main agent logic
│   │   │   ├── analyzers.py # Analysis implementations
│   │   │   ├── models.py    # Data models
│   │   │   ├── prompts. py   # LLM prompts
│   │   │   └── runner.py    # CLI runner
│   │   ├── execution/       # Execution Agent
│   │   │   ├── agent.py     # Main agent logic
│   │   │   ├── models.py    # Data models
│   │   │   ├── prompts.py   # LLM prompts
│   │   │   └── runner.py    # CLI runner
│   │   ├── llm/             # LLM integrations
│   │   │   ├── base.py      # Base LLM interface
│   │   │   ├── factory.py   # LLM factory
│   │   │   └── gemini_llm.py # Gemini implementation
│   │   ├── mcp_client/      # MCP client for agents
│   │   │   └── client.py    # MCP tool caller
│   │   └── policy/          # Policy Agent
│   │       ├── agent. py     # Main agent logic
│   │       ├── models.py    # Data models
│   │       ├── prompts.py   # LLM prompts
│   │       └── runner.py    # CLI runner
│   ├── audit/               # Audit system (immudb)
│   │   ├── cli. py           # Audit CLI
│   │   ├── client.py        # immudb client
│   │   ├── logger.py        # Audit logger service
│   │   └── models.py        # Audit record models
│   ├── knowledge_graph/     # Neo4j knowledge graph
│   │   ├── cli.py           # Knowledge graph CLI
│   │   ├── client.py        # Neo4j client
│   │   ├── policies.py      # Policy storage
│   │   └── topology.py      # Topology management
│   ├── mcp_server/          # MCP Server implementation
│   │   ├── config.py        # Server configuration
│   │   ├── server.py        # Main server entry point
│   │   └── tools/           # MCP tool handlers
│   │       ├── diagnosis_handlers.py
│   │       ├── execution_handlers.py
│   │       ├── policy_handlers.py
│   │       ├── telemetry_handlers. py
│   │       └── topology_handlers.py
│   ├── models/              # Core data models
│   │   ├── network.py       # Network models (Node, Link, etc.)
│   │   └── policy.py        # Policy models
│   ├── orchestrator/        # LangGraph pipeline
│   │   ├── cli.py           # Orchestrator CLI
│   │   ├── models.py        # Pipeline models
│   │   ├── orchestrator.py  # Main orchestrator
│   │   ├── pipeline.py      # LangGraph pipeline
│   │   └── scheduler.py     # Scheduled execution
│   └── simulator/           # Network simulation
│       ├── anomaly_injector.py  # Anomaly injection
│       ├── log_generator.py     # Log generation
│       ├── network_sim.py       # Topology simulation
│       ├── runner.py            # Simulator CLI
│       └── telemetry_generator.py # Telemetry generation
├── tests/                   # Test suite
├── .env.example             # Example environment file
├── pyproject.toml           # Project configuration
└── README.md
```

---

## 🧩 Components

### Network Simulator

The simulator creates a realistic telco network topology for testing and development.

**Default Topology:**
```
        Internet
           │
       [Firewall]
           │
     [Core Router 1]────[Core Router 2]
           │                   │
    [Dist Switch 1]     [Dist Switch 2]
        │     │             │     │
    [Access1][Access2] [Access3][Access4]
           │                   │
       [Server1]           [Server2]
```

**Supported Node Types:**
- `router_core` - Core routers (Cisco ASR-9000)
- `router_edge` - Edge routers
- `switch_distribution` - Distribution switches (Juniper QFX5100)
- `switch_access` - Access switches (Arista 7050X)
- `server` - Servers (Dell PowerEdge)
- `firewall` - Firewalls (Palo Alto PA-5220)
- `load_balancer` - Load balancers (F5 BIG-IP)

**Anomaly Types:**
| Type | Description |
|------|-------------|
| `HIGH_CPU` | CPU utilization spike |
| `MEMORY_LEAK` | Gradual memory increase |
| `INTERFACE_DOWN` | Network interface failure |
| `PACKET_LOSS` | Packet loss on links |
| `HIGH_LATENCY` | Increased network latency |
| `AUTH_FAILURE` | Authentication failures |
| `CONFIG_DRIFT` | Configuration changes |
| `SERVICE_DEGRADATION` | Service performance issues |
| `DISK_FULL` | Disk space exhaustion |
| `TEMPERATURE_HIGH` | Thermal warnings |

### Knowledge Graph (Neo4j)

Stores network topology, policies, and relationships for intelligent querying. 

**Node Labels:**
- `NetworkNode` - Physical/virtual network devices
- `Policy` - Automation policies
- `ComplianceRule` - Compliance requirements

**Relationships:**
- `CONNECTS_TO` - Network links between nodes
- `APPLIES_TO` - Policy targeting
- `DEPENDS_ON` - Dependency relationships

**Example Queries:**
```cypher
// Find all critical nodes
MATCH (n: NetworkNode)
WHERE n.type IN ['router_core', 'firewall']
RETURN n

// Get node dependencies
MATCH (n:NetworkNode {id: 'router_core_01'})<-[:CONNECTS_TO*]-(dependent)
RETURN dependent

// Find shortest path
MATCH path = shortestPath(
  (a:NetworkNode {id: 'server_01'})-[:CONNECTS_TO*]-(b:NetworkNode {id: 'firewall_01'})
)
RETURN path
```

### MCP Server

Exposes network operations as MCP tools that AI agents can call.

**Available Tools:**

| Category | Tool | Description |
|----------|------|-------------|
| **Telemetry** | `get_node_metrics` | Get metrics for a node or all nodes |
| | `get_network_logs` | Retrieve recent network logs |
| | `get_alerts` | Get active alerts |
| **Topology** | `get_network_topology` | Get full network topology |
| | `get_node_info` | Get detailed node information |
| | `get_connected_nodes` | Find connected nodes |
| **Diagnosis** | `run_diagnosis` | Run network diagnosis |
| | `get_anomalies` | Get active anomalies |
| | `inject_test_anomaly` | Inject test anomaly |
| | `clear_anomaly` | Clear anomalies |
| **Policy** | `get_policies` | Get available policies |
| | `evaluate_policy` | Evaluate policy against context |
| **Execution** | `execute_action` | Execute remediation action |
| | `verify_action` | Verify action outcome |

### AI Agents

#### Discovery Agent
Monitors the network and detects issues. 

```python
from src. agents.discovery import DiscoveryAgent

agent = DiscoveryAgent()
result = await agent.run(use_llm=True)

if result.success:
    report = result.result
    print(f"Found {len(report. issues)} issues")
    for issue in report. issues:
        print(f"  - {issue.issue_type}: {issue.node_id} ({issue.severity})")
```

#### Policy Agent
Evaluates policies and recommends actions.

```python
from src.agents. policy import PolicyAgent

agent = PolicyAgent()
result = await agent.evaluate(diagnosis_report, use_llm=True)

if result.success:
    recommendation = result.result
    for action in recommendation.recommended_actions:
        print(f"  - {action.action_type} on {action.target_node_id}")
```

#### Compliance Agent
Validates actions against compliance rules.

```python
from src.agents.compliance import ComplianceAgent

agent = ComplianceAgent()
result = await agent.validate(recommendation, use_llm=True)

if result.success:
    compliance = result.result
    print(f"Approved: {compliance.approved_count}")
    print(f"Denied:  {compliance.denied_count}")
```

#### Execution Agent
Executes approved remediation actions. 

```python
from src.agents.execution import ExecutionAgent

agent = ExecutionAgent()
result = await agent.execute(compliance_result, verify=True, dry_run=False)

if result.success:
    execution = result.result
    print(f"Success: {execution.success_count}/{execution.total_actions}")
```

### Orchestrator Pipeline

LangGraph-based pipeline that coordinates all agents.

```python
from src. orchestrator.pipeline import Pipeline, PipelineConfig

config = PipelineConfig(
    use_llm=True,
    dry_run=False,
    verify_execution=True,
)

pipeline = Pipeline(config)
run = await pipeline.execute(trigger="scheduled", triggered_by="scheduler")

print(run.get_summary())
```

### Audit System (immudb)

Provides immutable audit logging for all agent actions.

**Record Types:**
- `INTENT` - What the agent intends to do (logged before execution)
- `RESULT` - What happened after execution
- `DENIAL` - Actions that were blocked by compliance

```python
from src. audit.logger import AuditLogger

audit = AuditLogger()
audit.connect()

# Log intent
audit.log_intent(
    action_type="restart_service",
    target_node_id="router_core_01",
    reason="High CPU detected",
)

# Log result
audit.log_result(
    action_type="restart_service",
    target_node_id="router_core_01",
    success=True,
    duration_ms=1500,
)

# Query records
intents = audit.get_intents(limit=10)
```

---

# / > CLI Commands

## Network Simulator CLI Reference

The `network-sim` command generates synthetic network data (logs, telemetry) and simulates faults. It is used to feed the Knowledge Graph and test the Agents without requiring physical hardware.


### General Usage

```bash
network-sim [COMMAND] [OPTIONS]
```

### Topology Visualization

View the simulated network structure (nodes, links, and bandwidth).

```bash
# View summary table
network-sim show-topology

# Export topology structure to JSON
network-sim show-topology --format json
```

### Data Generation (Snapshot)

Generate static batches of data for testing ingestion pipelines.

**Generate Logs**
Create synthetic syslog/application logs.
```bash
# Generate 100 logs covering the last 60 minutes
network-sim generate-logs --count 100 --time-range 60

# Save to file
network-sim generate-logs --output ./data/logs.json
```

**Generate Telemetry**
Create a snapshot of current metrics (CPU, Memory, Latency) for all nodes.
```bash
# Print to console
network-sim generate-telemetry

# Save to file
network-sim generate-telemetry --output ./data/metrics.json
```

### Fault Injection (Chaos Engineering)

Simulate network failures to trigger Agent responses.

**Inject Specific Anomaly**
Target a specific node with a specific fault.
```bash
# Syntax
network-sim inject-anomaly --node [NODE_ID] --type [TYPE] --severity [LEVEL]

# Example: Spike CPU on a core router
network-sim inject-anomaly --node router_core_01 --type high_cpu --severity critical

# Example: Introduce packet loss and show generated logs immediately
network-sim inject-anomaly --node switch_dist_02 --type packet_loss --show-logs
```

**Inject Complex Scenario**
Trigger a pre-defined sequence of failures (e.g., "Data Center Power Failure").
```bash
# List available scenarios
network-sim list-scenarios

# Run a scenario
network-sim inject-scenario --scenario cascade_failure_01
```

**Reset State**
Clear all active anomalies and return nodes to "Healthy" status.
```bash
network-sim clear-anomalies
```

### Continuous Simulation

Run the simulator in "live" mode, continuously generating data and randomly injecting faults over time.

```bash
# Run for 60 seconds, updating every 2 seconds
network-sim run --duration 60 --interval 2

# Run indefinitely with random anomaly injection enabled
network-sim run --duration 0 --inject-anomalies --output-dir ./live_data/
```

## Knowledge Graph CLI Reference

The `knowledge-graph` command manages the Neo4j database, allowing you to visualize the network topology, find paths between nodes, and manage the policy engine definitions.

### Requirements

* **Neo4j Database**: Must be running locally or accessible via network.
    ```bash
    docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest
    ```
* **Python Dependencies**:
    ```bash
    pip install click rich neo4j
    ```

### General Usage

```bash
knowledge-graph [COMMAND] [OPTIONS]
```

### First-Time Setup

Run the "all-in-one" setup command to create database indexes, import the initial network topology from the simulator, and seed default policies.

```bash
knowledge-graph setup
```

### Connection & Maintenance

**Check Status**
Verify connectivity to the Neo4j database.
```bash
knowledge-graph status
```

**Database Operations**
```bash
# Initialize indexes (manual)
knowledge-graph init

# Clear the entire database (destructive)
knowledge-graph clear
```

### Topology Management

**View Network Topology**
Visualize the current state of the network.
```bash
# View as a table (default)
knowledge-graph topology show

# View as a hierarchical tree (grouped by device type)
knowledge-graph topology show --format tree

# Export as JSON
knowledge-graph topology show --format json
```

**Node Details**
Inspect a specific device's attributes and immediate connections.
```bash
knowledge-graph topology node [NODE_ID]
```

**Pathfinding**
Find the shortest path between two nodes in the graph.
```bash
knowledge-graph topology path [SOURCE_ID] [TARGET_ID]
```

**Critical Nodes**
List nodes currently marked as "Critical" or "Down".
```bash
knowledge-graph topology critical
```

### Policy Management

**List Policies**
View active rules stored in the graph.
```bash
# List all
knowledge-graph policies list

# Filter by status
knowledge-graph policies list --status active
```

**Policy Details**
View the specific conditions and remediation actions for a policy.
```bash
knowledge-graph policies show [POLICY_ID]
```

**Evaluate Policies (Dry Run)**
Test which policies would trigger given a specific set of conditions.
```bash
# Syntax
knowledge-graph policies evaluate --anomaly-type [TYPE] --severity [LEVEL] [OPTIONS]

# Example: Test High CPU response
knowledge-graph policies evaluate \
  --anomaly-type HIGH_CPU \
  --severity critical \
  --node-type router_core \
  --cpu 95
```

**Data Seeding**
```bash
# Seed default policies from YAML files
knowledge-graph policies seed

# Load specific policy file
knowledge-graph policies load ./custom_policies.yaml
```

## Discovery Agent CLI Reference

The `discovery-agent` command serves as the "eyes" of the system, continuously monitoring the network to detect anomalies, performance degradation, and faults using MCP tools and LLM analysis.


### General Usage

```bash
discovery-agent [COMMAND] [OPTIONS]
```

Use `--help` to see available commands:
```bash
discovery-agent --help
```

### Running Diagnosis

Trigger an immediate network scan. The agent will query network nodes via MCP, aggregate metrics, and perform root cause analysis.

```bash
# Run a full network-wide diagnosis
discovery-agent run

# Diagnose a specific node only
discovery-agent run --node router_core_01

# Run without LLM (Fast mode, raw metrics only)
discovery-agent run --no-llm

# Save the diagnosis report to JSON
discovery-agent run --output diagnosis_report.json --verbose
```

### Continuous Monitoring

Start a persistent process that runs diagnosis cycles at set intervals.

```bash
# Start watching (uses default interval from config)
discovery-agent watch

# Watch with a custom interval (e.g., every 5 minutes)
discovery-agent watch --interval 5

# Watch in fast mode (no LLM cost)
discovery-agent watch --no-llm
```

### Anomaly Management

Commands to view current network health and simulate faults for testing.

**View Active Anomalies**
List all currently detected issues that have not been resolved.
```bash
discovery-agent anomalies
```

**Inject Test Anomaly**
Simulate a fault to test the system's response (Chaos Engineering).
```bash
# Syntax
discovery-agent inject [NODE_ID] [ANOMALY_TYPE] [OPTIONS]

# Example: Simulate high latency on a switch
discovery-agent inject switch_05 high_latency --severity high
```

**Clear Anomalies**
Manually reset the anomaly database (useful after testing).
```bash
discovery-agent clear
```

### System Status & Tools

**Check Agent Status**
View LLM connectivity, configured intervals, and MCP tool availability.
```bash
discovery-agent status
```

**List MCP Tools**
View the specific capabilities (tools) the agent can currently access.
```bash
discovery-agent tools
```

## Policy Agent CLI Reference

The `policy-agent` command translates diagnostic data into concrete action plans. It evaluates network issues against business rules to determine the best course of action.

### General Usage

```bash
policy-agent [COMMAND] [OPTIONS]
```

Use `--help` to see available commands:
```bash
policy-agent --help
```

### Pipeline Execution

Run the policy evaluation pipeline. This triggers Discovery first to find issues, then evaluates those issues to generate recommendations.

```bash
# Run the pipeline (Discovery → Policy)
policy-agent run

# Save recommendations to a JSON file
policy-agent run --output policy_recommendations.json --verbose

# Run without LLM (Fast, rule-based only)
policy-agent run --no-llm
```

### Single Issue Evaluation

Manually input a hypothetical or specific issue to see what the Policy Agent would recommend.

```bash
# Syntax
policy-agent evaluate [ISSUE_TYPE] [SEVERITY] [NODE_ID] [OPTIONS]

# Example: What should we do if a core router has high latency?
policy-agent evaluate high_latency critical router_core_01 --node-type router_core

# Example: Check policy for a minor switch port error
policy-agent evaluate port_error low switch_access_05
```

### Policy Management

**List Active Policies**
View all currently loaded policies and their priorities.
```bash
policy-agent policies
```

**View Policy Details**
See the specific conditions and actions defined for a single policy.
```bash
policy-agent policy [POLICY_ID]
```

### Monitoring

**Check Agent Status**
View LLM connectivity and available policy tools.
```bash
policy-agent status
```

## Compliance Agent CLI Reference

The `compliance-agent` command serves as the "Gatekeeper" of the network, validating all proposed actions against safety rules, maintenance windows, and corporate policies before execution is allowed.

### Requirements

```bash
pip install click rich
```

### General Usage

```bash
compliance-agent [COMMAND] [OPTIONS]
```

Use `--help` to see available commands:
```bash
compliance-agent --help
```

### Pipeline Validation

Run the validation pipeline. This triggers Discovery and Policy generation first, then validates the resulting recommendations.

```bash
# Run the full pipeline (Discovery → Policy → Compliance)
compliance-agent run

# Save the compliance report to JSON
compliance-agent run --output compliance_report.json --verbose

# Run without LLM (Fast, rule-based only)
compliance-agent run --no-llm
```

### Single Action Validation

Manually check if a specific action would be allowed on a specific node without running the full pipeline.

```bash
# Syntax
compliance-agent validate [ACTION_TYPE] [TARGET_NODE_ID] [OPTIONS]

# Example: Check if restarting a router is allowed right now
compliance-agent validate restart_device router_01 --reason "User reported latency"

# Check without invoking the LLM
compliance-agent validate firmware_upgrade switch_05 --no-llm
```

### Rules & Constraints

**List Compliance Rules**
View the active set of rules (e.g., "No restarts on Core Routers during business hours").
```bash
compliance-agent rules
```

**Check Maintenance Window**
Check if the current time falls within an approved maintenance window (required for high-impact actions).
```bash
compliance-agent window
```

### Monitoring

**Check Agent Status**
View LLM connectivity, active rate limits, and current maintenance window status.
```bash
compliance-agent status
```

## Execution Agent CLI Reference

The `execution-agent` command controls the automated execution pipeline, allowing for full autonomous runs or specific manual actions on network nodes.


### General Usage

```bash
execution-agent [COMMAND] [OPTIONS]
```

Use `--help` to see available commands:
```bash
execution-agent --help
```

### Full Pipeline Execution

Run the complete autonomous cycle: **Discovery → Policy → Compliance → Execution**.

```bash
# Run the full pipeline (Live Execution)
execution-agent run

# Simulation Mode (Safe for testing)
# Runs the full pipeline but simulates the final execution steps
execution-agent run --dry-run

# Run without post-execution verification
execution-agent run --no-verify

# Save detailed results to a JSON file
execution-agent run --output execution_report.json --verbose
```

### Manual Action Execution

Bypass the pipeline to execute a specific action on a specific node directly.

```bash
# Syntax
execution-agent execute [ACTION_TYPE] [TARGET_NODE_ID] [OPTIONS]

# Example: Restart a specific router
execution-agent execute restart_device router_01 --reason "Maintenance window"

# Simulate a specific action (Dry Run)
execution-agent execute update_firmware switch_core_05 --dry-run
```

### Monitoring & History

**Check Agent Status**
View LLM connection, MCP tool availability, and current settings.
```bash
execution-agent status
```

**View Execution History**
See a log of past actions, their status (Success/Failed), and duration.
```bash
# View last 20 executions (default)
execution-agent history

# View last 50 executions
execution-agent history --limit 50
```

## Audit CLI Reference

The Audit CLI allows for querying and managing immutable audit records directly via the `audit` command defined in `pyproject.toml`.

### General Usage

```bash
audit [COMMAND] [OPTIONS]
```

Use `--help` to see available commands:
```bash
audit --help
```

### System Monitoring

**Check Status**
View database mode, connectivity, and total record counts.
```bash
audit status
```

**View Summary Report**
View success rates, verification rates, and recent performance metrics.
```bash
audit summary
```

### Viewing Records

**List All Records**
View a timeline of all audit events.
```bash
# Default (20 records)
audit list

# Filter by type (intent, result, denial)
audit list --type denial

# Show detailed JSON content
audit list --verbose
```

**Quick Filters**
Shortcuts for specific record tables.
```bash
# View proposed actions
audit intents --limit 50

# View execution results (Success/Fail)
audit results

# View blocked actions
audit denials
```

### Record Verification

Retrieve a specific record by ID and verify its cryptographic integrity.

```bash
audit get <RECORD_KEY> --verify
```

### Exporting Data

Export audit logs to file for external analysis.

```bash
# Export to JSON
audit export --output audit_export.json

# Export to CSV
audit export --format csv --output audit_export.csv --limit 5000
```

## Orchestrator CLI Reference

The `orchestrator` command acts as the central coordinator, tying together all agents (Discovery, Policy, Compliance, Execution) into a unified automation pipeline.

### Requirements

```bash
pip install click rich
```

### General Usage

```bash
orchestrator [COMMAND] [OPTIONS]
```

### Running the Pipeline

**Single Run (Manual Trigger)**
Run the entire pipeline once from start to finish.
```bash
# Run full pipeline (Live)
orchestrator run

# Run simulation only (Dry Run)
orchestrator run --dry-run

# Run without LLM analysis (Faster, rule-based only)
orchestrator run --no-llm

# Skip the final execution step (Discovery -> Policy -> Compliance only)
orchestrator run --skip-execution
```

**Continuous Mode (Daemon)**
Start the orchestrator as a service that runs the pipeline at set intervals.
```bash
# Run every 5 minutes (default)
orchestrator start

# Run every 15 minutes
orchestrator start --interval 15

# Run in safe mode (Dry Run + No Verification)
orchestrator start --dry-run --no-verify
```

### Monitoring & Configuration

**View Run History**
See a log of recent pipeline executions and their outcomes.
```bash
orchestrator history --limit 20
```

**View Configuration**
Show the current default settings loaded from environment variables.
```bash
orchestrator config
```

**Visualize Pipeline**
Display the LangGraph structure of the automation pipeline.
```bash
orchestrator graph
```

**Check Status**
View instructions for checking the status of running instances.
```bash
orchestrator status
```



---

## 📚 API Reference

### Data Models

#### Node
```python
class Node(BaseModel):
    id: str                    # Unique identifier
    name: str                  # Human-readable name
    type: NodeType             # Device type
    ip_address: str            # Management IP
    location: str              # Physical location
    status: NodeStatus         # Operational status
    vendor: str                # Equipment vendor
    model: str                 # Equipment model
    interfaces: list[str]      # Network interfaces
    metadata: dict             # Additional metadata
```

#### DetectedIssue
```python
class DetectedIssue(BaseModel):
    issue_id: str              # Unique issue ID
    issue_type: IssueType      # Type of issue
    severity: IssueSeverity    # Severity level
    node_id:  str               # Affected node
    node_name: str             # Node name
    node_type: str             # Node type
    detected_at: datetime      # Detection time
    description:  str           # Issue description
    current_value: float       # Current metric value
    threshold: float           # Threshold exceeded
    recommended_action: str    # Suggested action
    metadata:  dict             # Additional context
```

#### Policy
```python
class Policy(BaseModel):
    id: str                    # Policy ID
    name:  str                  # Policy name
    policy_type: PolicyType    # Type (remediation, compliance, etc.)
    conditions: list[Condition]  # Trigger conditions
    actions:  list[PolicyAction]  # Actions to take
    priority: int              # Priority (lower = higher)
    status: PolicyStatus       # Active/inactive
```

---



### Setup Development Environment

```bash
# Install with dev dependencies
pip install -e ".[dev]"

```


### Running Tests

```bash

# Run specific test file
pytest tests/test_discovery_agent.py -v
```

---

## 🗺 Roadmap

### Phase 1 ✅ (Current)
- [x] Network simulator with topology generation
- [x] Neo4j knowledge graph integration
- [x] MCP server with core tools
- [x] Four AI agents (Discovery, Policy, Compliance, Execution)
- [x] LangGraph orchestration pipeline
- [x] immudb audit trail

### Phase 2 (Planned)
- [ ] Multi-LLM support (Claude, GPT-4, local models)
- [ ] Redis-based state management
- [ ] Real network device integration (SNMP, NETCONF)
- [ ] Web dashboard for monitoring
- [ ] Kubernetes deployment manifests


---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent orchestration framework
- [Model Context Protocol](https://modelcontextprotocol. io/) - Tool interface standard
- [Neo4j](https://neo4j.com/) - Graph database
- [immudb](https://immudb.io/) - Immutable database
- [Pydantic](https://pydantic.dev/) - Data validation

---