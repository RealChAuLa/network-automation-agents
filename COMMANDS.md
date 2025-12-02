# Terminal Commands Summary

This document contains all the terminal commands needed to set up and run the Network Automation Simulator, as requested.

## Step-by-Step Terminal Commands

### Step 1: Create a Python Virtual Environment (Python 3.11+)

```bash
cd /home/runner/work/network-automation-agents/network-automation-agents
python -m venv venv
```

### Step 2: Install Dependencies from pyproject.toml (including dev dependencies)

```bash
# Activate the virtual environment
source venv/bin/activate  # On Linux/macOS
# OR
venv\Scripts\activate     # On Windows

# Upgrade pip
pip install --upgrade pip

# Install the project with dev dependencies
pip install -e ".[dev]"
```

### Step 3: Copy .env.example to .env

```bash
cp .env.example .env
```

### Step 4: Verify the Installation

#### Show the network topology:
```bash
python -m src.simulator.runner show-topology
```

#### Generate a batch of logs (50 entries):
```bash
python -m src.simulator.runner generate-batch --count 50
```

#### Run continuous simulation for 30 seconds:
```bash
python -m src.simulator.runner run --interval 5 --duration 30
```

### Step 5: Run the Tests

```bash
pytest
```

For verbose output:
```bash
pytest -v
```

With coverage:
```bash
pytest --cov=src
```

## Additional Commands

### Code Formatting

```bash
# Check formatting
black --check .

# Apply formatting
black .
```

### Code Linting

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .
```

### Deactivate Virtual Environment

```bash
deactivate
```

## All-in-One Setup Script

Here's a complete script to run all setup steps:

```bash
# Navigate to project directory
cd /home/runner/work/network-automation-agents/network-automation-agents

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -e ".[dev]"

# Copy environment file
cp .env.example .env

# Verify installation - show topology
echo "=== Testing: Show Topology ==="
python -m src.simulator.runner show-topology

# Verify installation - generate batch
echo "=== Testing: Generate Batch ==="
python -m src.simulator.runner generate-batch --count 50

# Verify installation - run simulation
echo "=== Testing: Run Simulation ==="
python -m src.simulator.runner run --interval 5 --duration 30

# Run tests
echo "=== Running Tests ==="
pytest -v
```

## Verification Checklist

After running the commands above, you should see:

- ✅ Virtual environment created in `venv/` directory
- ✅ All dependencies installed without errors
- ✅ `.env` file exists with configuration
- ✅ `show-topology` command displays network devices
- ✅ `generate-batch` command produces JSON log entries
- ✅ `run` command executes continuous simulation
- ✅ All tests pass (14 tests)

## Expected Test Output

```
================================================= test session starts ==================================================
platform linux -- Python 3.12.3, pytest-9.0.1, pluggy-1.6.0
rootdir: /home/runner/work/network-automation-agents/network-automation-agents
configfile: pyproject.toml
testpaths: tests
plugins: Faker-38.2.0, cov-7.0.0
collected 14 items

tests/test_simulator/test_log_generator.py::test_log_generator_init PASSED                    [  7%]
tests/test_simulator/test_log_generator.py::test_generate_log PASSED                          [ 14%]
tests/test_simulator/test_log_generator.py::test_generate_batch PASSED                        [ 21%]
tests/test_simulator/test_log_generator.py::test_get_facility_by_device_type PASSED           [ 28%]
tests/test_simulator/test_network_sim.py::test_network_simulator_init PASSED                  [ 35%]
tests/test_simulator/test_network_sim.py::test_generate_topology PASSED                       [ 42%]
tests/test_simulator/test_network_sim.py::test_get_topology_creates_if_none PASSED            [ 50%]
tests/test_simulator/test_network_sim.py::test_device_properties PASSED                       [ 57%]
tests/test_simulator/test_network_sim.py::test_topology_device_count PASSED                   [ 64%]
tests/test_simulator/test_network_sim.py::test_get_device_by_id PASSED                        [ 71%]
tests/test_simulator/test_telemetry_generator.py::test_telemetry_generator_init PASSED        [ 78%]
tests/test_simulator/test_telemetry_generator.py::test_generate_telemetry_normal PASSED       [ 85%]
tests/test_simulator/test_telemetry_generator.py::test_generate_telemetry_with_anomaly PASSED [ 92%]
tests/test_simulator/test_telemetry_generator.py::test_generate_batch PASSED                  [100%]

================================================== 14 passed in 0.08s ==================================================
```

## Troubleshooting

### Issue: Command not found
**Solution**: Make sure the virtual environment is activated.

### Issue: Module not found
**Solution**: Reinstall dependencies with `pip install -e ".[dev]"`

### Issue: Permission denied
**Solution**: Ensure you have write permissions in the project directory.

### Issue: Tests fail
**Solution**: 
1. Check that `.env` file exists
2. Verify all dependencies are installed
3. Run `pytest -v` for detailed error messages
