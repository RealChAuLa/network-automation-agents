# Development Environment Setup Guide

This guide provides step-by-step terminal commands to set up the development environment for the Network Automation Simulator project.

## Prerequisites

- Python 3.11 or higher
- pip (Python package installer)
- Git

## Setup Steps

### 1. Clone the Repository (if not already done)

```bash
git clone https://github.com/RealChAuLa/network-automation-agents.git
cd network-automation-agents
```

### 2. Create a Python Virtual Environment

```bash
python -m venv venv
```

### 3. Activate the Virtual Environment

**On Linux/macOS:**
```bash
source venv/bin/activate
```

**On Windows:**
```bash
venv\Scripts\activate
```

### 4. Upgrade pip

```bash
pip install --upgrade pip
```

### 5. Install Dependencies

Install the project with development dependencies:

```bash
pip install -e ".[dev]"
```

This will install:
- **Core dependencies**: python-dotenv, click, pyyaml, faker
- **Development dependencies**: pytest, pytest-cov, black, ruff

### 6. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

You can edit `.env` to customize the simulation settings if needed.

## Verify Installation

### Show Network Topology

Display the simulated network topology:

```bash
python -m src.simulator.runner show-topology
```

Expected output: A formatted display of routers, switches, and firewalls in the network.

### Generate Log Batch

Generate a batch of network device logs:

```bash
python -m src.simulator.runner generate-batch --count 50
```

Expected output: 50 JSON-formatted log entries from various network devices.

### Run Continuous Simulation

Run the simulator continuously for 30 seconds with 5-second intervals:

```bash
python -m src.simulator.runner run --interval 5 --duration 30
```

Expected output: Continuous generation of logs, telemetry, and anomaly detection for 30 seconds.

## Run Tests

Execute the test suite:

```bash
pytest
```

For verbose output:

```bash
pytest -v
```

For test coverage:

```bash
pytest --cov=src
```

## Code Quality

### Format Code

Format code using Black:

```bash
black .
```

### Lint Code

Check code with Ruff:

```bash
ruff check .
```

Auto-fix issues:

```bash
ruff check --fix .
```

## Project Structure

```
network-automation-agents/
├── README.md                  # Project documentation
├── pyproject.toml            # Project configuration and dependencies
├── .env.example              # Example environment variables
├── .env                      # Environment variables (not committed)
├── .gitignore               # Git ignore rules
├── src/
│   ├── __init__.py
│   ├── simulator/
│   │   ├── __init__.py
│   │   ├── network_sim.py          # Network topology simulator
│   │   ├── log_generator.py        # Log generation
│   │   ├── telemetry_generator.py  # Telemetry data generation
│   │   ├── anomaly_injector.py     # Anomaly injection
│   │   └── runner.py               # CLI interface
│   └── models/
│       ├── __init__.py
│       └── network.py              # Network device models
└── tests/
    ├── conftest.py                 # Test configuration
    └── test_simulator/
        ├── __init__.py
        ├── test_network_sim.py
        ├── test_log_generator.py
        └── test_telemetry_generator.py
```

## Available CLI Commands

The simulator provides the following commands:

1. **show-topology** - Display the network topology
2. **generate-batch** - Generate a batch of logs
   - `--count`: Number of logs to generate (default: 10)
3. **run** - Run continuous simulation
   - `--interval`: Seconds between iterations (default: 5)
   - `--duration`: Total runtime in seconds (default: 60)

## Troubleshooting

### Virtual Environment Not Activating

If the virtual environment doesn't activate, ensure you're using the correct command for your operating system (see step 3).

### Import Errors

If you encounter import errors, make sure:
1. The virtual environment is activated
2. Dependencies are installed (`pip install -e ".[dev]"`)
3. You're running commands from the project root directory

### Tests Failing

If tests fail:
1. Ensure all dependencies are installed
2. Check that `.env` file exists (copy from `.env.example` if missing)
3. Run `pytest -v` for detailed error messages

## Deactivating the Virtual Environment

When you're done working on the project:

```bash
deactivate
```

## Next Steps

- Review the README.md for project overview
- Explore the code in `src/simulator/`
- Add new test cases in `tests/test_simulator/`
- Customize simulation parameters in `.env`
