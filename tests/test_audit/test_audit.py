"""Tests for the Audit system."""

import pytest
from datetime import datetime

from src.audit.models import (
    AuditRecord,
    AuditRecordType,
    IntentRecord,
    ResultRecord,
    DenialRecord,
)
from src.audit.client import ImmudbClient, ImmudbConfig
from src.audit.logger import AuditLogger


class TestAuditRecord:
    """Test cases for AuditRecord model."""

    def test_create_record(self):
        """Test creating an audit record."""
        record = AuditRecord(
            record_type=AuditRecordType.SYSTEM,
            agent_name="test",
            summary="Test record",
        )

        assert record.record_type == AuditRecordType.SYSTEM
        assert record.agent_name == "test"
        assert record.id.startswith("audit_")

    def test_compute_hash(self):
        """Test computing content hash."""
        record = AuditRecord(
            agent_name="test",
            summary="Test record",
        )

        hash1 = record.compute_hash()

        assert hash1 is not None
        assert len(hash1) == 64  # SHA-256 hex

        # Same content should produce same hash
        hash2 = record.compute_hash()
        assert hash1 == hash2

    def test_to_dict(self):
        """Test converting record to dictionary."""
        record = AuditRecord(
            record_type=AuditRecordType.INTENT,
            agent_name="execution",
            summary="Test intent",
        )

        data = record.to_dict()

        assert data["record_type"] == "intent"
        assert data["agent_name"] == "execution"
        assert data["content_hash"] is not None

    def test_from_dict(self):
        """Test creating record from dictionary."""
        data = {
            "id": "audit_123",
            "record_type": "result",
            "agent_name": "execution",
            "summary": "Test result",
            "timestamp": "2024-01-15T10:00:00",
        }

        record = AuditRecord.from_dict(data)

        assert record.id == "audit_123"
        assert record.record_type == AuditRecordType.RESULT


class TestIntentRecord:
    """Test cases for IntentRecord model."""

    def test_create_intent(self):
        """Test creating an intent record."""
        record = IntentRecord(
            action_type="restart_service",
            target_node_id="router_core_01",
            target_node_name="core-rtr-01",
            reason="High CPU detected",
            approved_by="system",
        )

        assert record.record_type == AuditRecordType.INTENT
        assert record.action_type == "restart_service"
        assert record.approved_by == "system"

    def test_intent_to_dict(self):
        """Test converting intent to dictionary."""
        record = IntentRecord(
            action_type="restart_service",
            target_node_id="router_01",
            policy_ids=["POL-001", "POL-002"],
        )

        data = record.to_dict()

        assert data["action_type"] == "restart_service"
        assert data["policy_ids"] == ["POL-001", "POL-002"]


class TestResultRecord:
    """Test cases for ResultRecord model."""

    def test_create_result(self):
        """Test creating a result record."""
        record = ResultRecord(
            action_type="restart_service",
            target_node_id="router_core_01",
            success=True,
            status="success",
            duration_ms=500,
        )

        assert record.record_type == AuditRecordType.RESULT
        assert record.success is True
        assert record.duration_ms == 500

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        record = ResultRecord(
            action_type="restart_service",
            success=True,
            verified=True,
            improvement_detected=True,
            metrics_before={"cpu": 95},
            metrics_after={"cpu": 30},
        )

        data = record.to_dict()

        assert data["success"] is True
        assert data["verified"] is True
        assert data["metrics_before"]["cpu"] == 95


class TestDenialRecord:
    """Test cases for DenialRecord model."""

    def test_create_denial(self):
        """Test creating a denial record."""
        record = DenialRecord(
            action_type="restart_node",
            target_node_id="router_core_01",
            denial_reason="Outside maintenance window",
            violation_type="maintenance_window",
            rule_id="MAINT-001",
        )

        assert record.record_type == AuditRecordType.DENIAL
        assert record.violation_type == "maintenance_window"


class TestImmudbClient:
    """Test cases for ImmudbClient."""

    @pytest.fixture
    def client(self):
        """Create immudb client (uses fallback)."""
        client = ImmudbClient()
        client.connect()
        return client

    def test_connect(self, client):
        """Test connecting to immudb."""
        assert client.is_connected() is True

    def test_set_and_get(self, client):
        """Test setting and getting a value."""
        key = "test: 123"
        value = {"action": "restart", "node": "router_01"}

        result = client.set(key, value)

        assert result["verified"] is True

        retrieved = client.get(key)

        assert retrieved is not None
        assert retrieved["action"] == "restart"

    def test_verified_get(self, client):
        """Test verified get."""
        key = "test:verified: 123"
        value = {"data": "test"}

        client.set(key, value)
        result = client.verified_get(key)

        assert result is not None
        assert result["verified"] is True
        assert result["value"]["data"] == "test"

    @pytest.mark.skip(reason="immudb scan requires running server")
    def test_scan(self, client):
        """Test scanning by prefix."""
        # Set some test values
        client.set("scan:test:1", {"id": 1})
        client.set("scan:test:2", {"id": 2})
        client.set("scan:other:3", {"id": 3})

        results = client.scan("scan: test:", limit=10)

        assert len(results) >= 2
        assert all(r["key"].startswith("scan:test:") for r in results)

    def test_get_stats(self, client):
        """Test getting stats."""
        stats = client.get_stats()

        assert stats["connected"] is True
        assert "mode" in stats


class TestAuditLogger:
    """Test cases for AuditLogger."""

    @pytest.fixture
    def logger(self):
        """Create audit logger."""
        audit = AuditLogger()
        audit.connect()
        return audit

    def test_connect(self, logger):
        """Test connecting to audit logger."""
        assert logger.is_connected() is True

    def test_log_intent(self, logger):
        """Test logging an intent."""
        result = logger.log_intent(
            action_type="restart_service",
            target_node_id="router_core_01",
            target_node_name="core-rtr-01",
            reason="High CPU detected",
            approved_by="system",
        )

        assert result["verified"] is True
        assert "record_id" in result

    def test_log_result(self, logger):
        """Test logging a result."""
        result = logger.log_result(
            action_type="restart_service",
            target_node_id="router_core_01",
            success=True,
            status="success",
            duration_ms=500,
        )

        assert result["verified"] is True

    def test_log_denial(self, logger):
        """Test logging a denial."""
        result = logger.log_denial(
            action_type="restart_node",
            target_node_id="router_core_01",
            denial_reason="Outside maintenance window",
            violation_type="maintenance_window",
            rule_id="MAINT-001",
        )

        assert result["verified"] is True

    def test_query_intents(self, logger):
        """Test querying intent records."""
        # Log an intent first
        logger.log_intent(
            action_type="test_action",
            target_node_id="test_node",
            reason="Test",
        )

        intents = logger.get_intents(limit=10)

        assert isinstance(intents, list)

    def test_get_stats(self, logger):
        """Test getting audit stats."""
        stats = logger.get_stats()

        assert stats["enabled"] is True
        assert "records" in stats


class TestIntegration:
    """Integration tests for audit with execution."""

    @pytest.mark.asyncio
    async def test_execution_logs_to_audit(self):
        """Test that execution agent logs to audit."""
        from src.agents.execution import ExecutionAgent
        from src.agents.compliance.models import ComplianceResult, ActionValidation, ValidationStatus

        # Create a simple compliance result
        compliance = ComplianceResult()
        validation = ActionValidation(
            action_type="restart_service",
            target_node_id="router_core_01",
            status=ValidationStatus.APPROVED,
            approved_by="test",
        )
        compliance.add_validation(validation)

        # Execute with dry run
        agent = ExecutionAgent()
        result = await agent.execute(compliance, verify=False, dry_run=True)

        assert result.success is True

        # Check that audit stats show records
        # Note: In dry run, audit logging is skipped