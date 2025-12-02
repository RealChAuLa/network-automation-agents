"""Simulator runner CLI."""

import os
import time
import json
import click
from dotenv import load_dotenv
from src.simulator.network_sim import NetworkSimulator
from src.simulator.log_generator import LogGenerator
from src.simulator.telemetry_generator import TelemetryGenerator
from src.simulator.anomaly_injector import AnomalyInjector


# Load environment variables
load_dotenv()


@click.group()
def cli():
    """Network Automation Simulator CLI."""
    pass


@cli.command()
def show_topology():
    """Display the network topology."""
    simulator = NetworkSimulator()
    simulator.print_topology()


@cli.command()
@click.option("--count", default=10, help="Number of logs to generate")
def generate_batch(count):
    """Generate a batch of network logs."""
    simulator = NetworkSimulator()
    topology = simulator.get_topology()
    devices = topology.get_all_devices()

    log_generator = LogGenerator()
    logs = log_generator.generate_batch(devices, count)

    print(f"\nGenerated {len(logs)} log entries:\n")
    for log in logs:
        print(json.dumps(log, indent=2))


@cli.command()
@click.option("--interval", default=5, help="Interval between generations (seconds)")
@click.option("--duration", default=60, help="Total duration to run (seconds)")
def run(interval, duration):
    """Run continuous network simulation."""
    simulator = NetworkSimulator()
    topology = simulator.get_topology()
    devices = topology.get_all_devices()

    log_generator = LogGenerator()
    telemetry_generator = TelemetryGenerator()
    anomaly_injector = AnomalyInjector(
        anomaly_probability=float(os.getenv("ANOMALY_PROBABILITY", "0.1"))
    )

    print(f"\n{'=' * 80}")
    print("STARTING CONTINUOUS NETWORK SIMULATION")
    print(f"{'=' * 80}")
    print(f"Interval: {interval} seconds")
    print(f"Duration: {duration} seconds")
    print(f"Devices: {len(devices)}")
    print(f"{'=' * 80}\n")

    start_time = time.time()
    iteration = 0

    try:
        while time.time() - start_time < duration:
            iteration += 1
            print(f"\n--- Iteration {iteration} ({time.strftime('%H:%M:%S')}) ---")

            # Generate logs
            logs = log_generator.generate_batch(devices, count=5)
            print(f"\n✓ Generated {len(logs)} log entries")

            # Generate telemetry
            telemetry = telemetry_generator.generate_batch(devices, count=5)
            print(f"✓ Generated {len(telemetry)} telemetry entries")

            # Check for anomalies
            anomalies = []
            for device in devices:
                if anomaly_injector.should_inject_anomaly():
                    anomaly = anomaly_injector.generate_anomaly(device)
                    anomalies.append(anomaly)

            if anomalies:
                print(f"⚠ Detected {len(anomalies)} anomalies!")
                for anomaly in anomalies:
                    print(
                        f"  - {anomaly['anomaly_type']} on {anomaly['hostname']} "
                        f"[{anomaly['severity']}]"
                    )
            else:
                print("✓ No anomalies detected")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\nSimulation interrupted by user.")

    elapsed = time.time() - start_time
    print(f"\n{'=' * 80}")
    print(f"SIMULATION COMPLETED")
    print(f"{'=' * 80}")
    print(f"Total runtime: {elapsed:.1f} seconds")
    print(f"Iterations: {iteration}")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    cli()
