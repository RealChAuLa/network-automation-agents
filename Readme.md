# Network Automation Agents

A Python-based network automation simulation framework for testing AI agents in network management scenarios.

## Features

- **Network Topology Simulation**: Simulate routers, switches, and firewalls
- **Log Generation**: Generate realistic network device logs
- **Telemetry Data**: Generate network device telemetry (CPU, memory, bandwidth)
- **Anomaly Injection**: Inject network anomalies for testing detection systems

## Prerequisites

- Python 3.11 or higher
- pip (Python package installer)

## Installation

For detailed setup instructions, see [SETUP.md](SETUP.md).

Quick start:

1. Clone the repository:
```bash
git clone https://github.com/RealChAuLa/network-automation-agents.git
cd network-automation-agents
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e ".[dev]"
```

4. Copy the example environment file:
```bash
cp .env.example .env
```

## Usage

### Show Network Topology
```bash
python -m src.simulator.runner show-topology
```

### Generate Log Batch
```bash
python -m src.simulator.runner generate-batch --count 50
```

### Run Continuous Simulation
```bash
python -m src.simulator.runner run --interval 5 --duration 30
```

## Running Tests

```bash
pytest
```

## Development

To run linting:
```bash
black .
ruff check .
```

## License

MIT
