# Network Automation Agents

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python. org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Blockchain-secured MCP (Model Context Protocol) Registry for Telco Network Automation with AI Agents.

## 🎯 Overview

This project implements an autonomous network automation system for telecommunications infrastructure.  It uses AI agents to monitor, diagnose, and remediate network issues while maintaining a complete audit trail on an immutable blockchain. 

### Key Features

- **AI-Powered Agents**: Discovery, Policy, Execution, and Compliance agents work together autonomously
- **Blockchain Audit Trail**: All network executions are recorded immutably (using immudb)
- **MCP Integration**: Agents interact with network tools via Model Context Protocol
- **Policy-Based Actions**: Actions are only executed when approved by policy rules
- **Compliance Tracking**: Denied actions are logged for policy tuning and auditing

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA INGESTION                               │
│   [Log Simulator] → [SNMP/Telemetry] → [Message Queue]              │
└─────────────────────────────────────┬───────────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────────┐
│                         KNOWLEDGE LAYER                              │
│   [Knowledge Graph] ←→ [Network Topology] ←→ [Policy Rules]         │
└─────────────────────────────────────┬───────────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────────┐
│                         MCP SERVER                                   │
│   [Telemetry Tools] [Policy Tools] [Execution Tools] [Blockchain]    │
└─────────────────────────────────────┬───────────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────────┐
│                         AGENT LAYER                                  │
│   [Discovery] → [Policy] → [Compliance] → [Execution]                │
└─────────────────────────────────────┬───────────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────────┐
│                      IMMUTABLE LEDGER                                │
│   [immudb] ← Only execution records (Intent + Result)                │
└─────────────────────────────────────────────────────────────────────┘
```

## 📦 Project Structure

```
network-automation-agents/
├── src/
│   ├── simulator/          # Phase 1: Log & Telemetry Simulator
│   │   ├── network_sim.py
│   │   ├── log_generator.py
│   │   ├── telemetry_generator.py
│   │   ├── anomaly_injector.py
│   │   └── runner.py
│   ├── models/             # Shared data models
│   ├── blockchain/         # Phase 2: immudb integration
│   ├── knowledge_graph/    # Phase 3: Neo4j/NetworkX
│   ├── mcp_server/         # Phase 4: MCP tools
│   └── agents/             # Phase 5-9: AI Agents
├── policies/               # Policy definitions (YAML)
├── tests/                  # Test suite
└── scripts/                # Utility scripts
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- pip or uv package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/RealChAuLa/network-automation-agents.git
cd network-automation-agents

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### Running the Simulator

```bash
# Show network topology
python -m src.simulator.runner show-topology

# Generate batch of logs
python -m src.simulator.runner generate-logs --count 100 --output logs. json

# Generate telemetry snapshots
python -m src.simulator.runner generate-telemetry --output telemetry.json

# Inject an anomaly
python -m src.simulator. runner inject-anomaly --node router_core_01 --type HIGH_CPU --severity critical

# Inject a scenario
python -m src.simulator.runner inject-scenario --scenario ddos_attack

# Run continuous simulation
python -m src.simulator.runner run --interval 5 --duration 300 --inject-anomalies

# List available scenarios
python -m src.simulator.runner list-scenarios
```

## 🧪 Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_simulator/test_network_sim.py -v
```

## 📊 Simulator Features

### Network Topology

The simulator creates a realistic telco network with:
- **2 Core Routers** (Cisco ASR-9000)
- **1 Firewall** (Palo Alto PA-5220)
- **2 Distribution Switches** (Juniper QFX5100)
- **3 Access Switches** (Arista 7050X)
- **2 Servers** (Dell PowerEdge R750)
- **1 Load Balancer** (F5 BIG-IP)

### Log Generation

- Syslog-style logs with realistic messages
- Sources: system, interface, security, protocol
- Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Weighted distribution (more INFO, less CRITICAL)

### Telemetry Generation

- CPU & Memory utilization
- Bandwidth (in/out)
- Packet loss & latency
- Error counts & temperature
- SNMP OID references
- Time-of-day patterns

### Anomaly Injection

| Anomaly Type | Description | Affected Metrics |
|--------------|-------------|------------------|
| HIGH_CPU | CPU spike | cpu_utilization |
| MEMORY_LEAK | Memory increase | memory_utilization |
| INTERFACE_DOWN | Link failure | bandwidth_in, bandwidth_out |
| PACKET_LOSS | Network congestion | packet_loss, error_count |
| HIGH_LATENCY | Slow response | latency |
| AUTH_FAILURE | Security events | (logs only) |
| CONFIG_DRIFT | Unexpected changes | (logs only) |
| SERVICE_DEGRADATION | Multiple issues | cpu, latency, packet_loss |
| TEMPERATURE_HIGH | Cooling issues | temperature |

### Incident Scenarios

- `datacenter_cooling_failure` - Multiple nodes with high temperature
- `ddos_attack` - High CPU on edge devices
- `network_congestion` - Packet loss and latency
- `memory_leak_outbreak` - Memory issues on servers
- `link_failure` - Core link down
- `security_breach_attempt` - Auth failures across network

## 🗺️ Development Roadmap

| Phase | Component | Status |
|-------|-----------|--------|
| 1 | Log Simulator | ✅ Complete |
| 2 | immudb Integration | 🔲 Planned |
| 3 | Knowledge Graph | 🔲 Planned |
| 4 | MCP Server | 🔲 Planned |
| 5 | Discovery Agent | 🔲 Planned |
| 6 | Policy Agent | 🔲 Planned |
| 7 | Execution Agent | 🔲 Planned |
| 8 | Compliance Agent | 🔲 Planned |
| 9 | Orchestrator | 🔲 Planned |
| 10 | Integration | 🔲 Planned |

## 🔧 Configuration

Create a `.env` file based on `.env.example`:

```bash
cp .env.example . env
```

Available settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `SIMULATOR_OUTPUT_DIR` | Output directory for generated data | `./output` |
| `SIMULATOR_DEFAULT_INTERVAL` | Default interval in seconds | `5` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `REDIS_URL` | Redis connection URL (future) | `redis://localhost:6379` |
| `IMMUDB_HOST` | immudb host (Phase 2) | `localhost` |

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request