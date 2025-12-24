"""
Audit Logger

Service for logging audit records to immudb.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from dotenv import load_dotenv

from src.audit.client import ImmudbClient, ImmudbConfig
from src.audit.models import (
    AuditRecord,
    AuditRecordType,
    IntentRecord,
    ResultRecord,
    DenialRecord,
    AuditQuery,
)

load_dotenv()

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Audit logging service using immudb.

    Provides methods to log and query immutable audit records.

    Example:
        >>> audit = AuditLogger()
        >>> audit.connect()
        >>> audit.log_intent(
        ...     action_type="restart_service",
        ...     target_node_id="router_01",
        ...     reason="High CPU detected",
        ...  )
    """

    def __init__(self, client: Optional[ImmudbClient] = None):
        """
        Initialize audit logger.

        Args:
            client: immudb client (creates one if not provided)
        """
        self.client = client or ImmudbClient()
        self.enabled = os.getenv("AUDIT_ENABLED", "true").lower() == "true"
        self.log_intents = os.getenv("AUDIT_LOG_INTENTS", "true").lower() == "true"
        self.log_results = os.getenv("AUDIT_LOG_RESULTS", "true").lower() == "true"
        self.log_denials = os.getenv("AUDIT_LOG_DENIALS", "true").lower() == "true"

        self._connected = False

    def connect(self) -> bool:
        """Connect to immudb."""
        if not self.enabled:
            logger.info("Audit logging is disabled")
            return True

        result = self.client.connect()
        self._connected = result
        return result

    def disconnect(self):
        """Disconnect from immudb."""
        self.client.disconnect()
        self._connected = False

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    def _generate_key(self, record_type: AuditRecordType, record_id: str) -> str:
        """Generate a key for the record."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"audit:{record_type.value}:{timestamp}:{record_id}"

    def log_record(self, record: AuditRecord) -> dict:
        """
        Log a generic audit record.

        Args:
            record: The audit record to log

        Returns:
            Transaction info
        """
        if not self.enabled:
            return {"enabled": False}

        if not self._connected:
            self.connect()

        # Compute hash
        record.compute_hash()

        # Generate key
        key = self._generate_key(record.record_type, record.id)

        # Store
        result = self.client.set(key, record.to_dict())

        logger.info(f"Logged audit record: {record.record_type.value} - {record.id}")

        return {
            "key": key,
            "record_id": record.id,
            "record_type": record.record_type.value,
            "content_hash": record.content_hash,
            **result,
        }

    def log_intent(
            self,
            action_type: str,
            target_node_id: str,
            target_node_name: str = "",
            target_node_type: str = "",
            reason: str = "",
            original_issue_type: str = "",
            original_issue_severity: str = "",
            original_value: Optional[float] = None,
            policy_ids: List[str] = None,
            compliance_status: str = "",
            approved_by: str = "",
            expected_outcome: str = "",
            diagnosis_id: str = "",
            recommendation_id: str = "",
            compliance_id: str = "",
            action_id: str = "",
            execution_id: str = "",
            agent_name: str = "execution",
    ) -> dict:
        """
        Log an intent record (before action execution).

        Args:
            action_type:  Type of action to be executed
            target_node_id: Target node ID
            target_node_name:  Target node name
            target_node_type:  Type of target node
            reason: Reason for the action
            original_issue_type:  Type of issue that triggered this
            original_issue_severity: Severity of the original issue
            original_value: Original metric value
            policy_ids:  Policies that recommended this action
            compliance_status: Compliance check result
            approved_by: Who/what approved this action
            expected_outcome: Expected result
            diagnosis_id: Related diagnosis ID
            recommendation_id: Related recommendation ID
            compliance_id: Related compliance result ID
            action_id: Action ID
            execution_id:  Execution ID
            agent_name: Name of the agent

        Returns:
            Transaction info
        """
        if not self.log_intents:
            return {"enabled": False, "type": "intent"}

        record = IntentRecord(
            agent_name=agent_name,
            execution_id=execution_id,
            diagnosis_id=diagnosis_id,
            recommendation_id=recommendation_id,
            compliance_id=compliance_id,
            action_id=action_id,
            action_type=action_type,
            target_node_id=target_node_id,
            target_node_name=target_node_name,
            target_node_type=target_node_type,
            reason=reason,
            original_issue_type=original_issue_type,
            original_issue_severity=original_issue_severity,
            original_value=original_value,
            policy_ids=policy_ids or [],
            compliance_status=compliance_status,
            approved_by=approved_by,
            expected_outcome=expected_outcome,
            summary=f"Intent: {action_type} on {target_node_id}",
        )

        return self.log_record(record)

    def log_result(
            self,
            action_type: str,
            target_node_id: str,
            target_node_name: str = "",
            success: bool = False,
            status: str = "",
            result_message: str = "",
            error_message: str = "",
            started_at: Optional[datetime] = None,
            completed_at: Optional[datetime] = None,
            duration_ms: Optional[int] = None,
            retry_count: int = 0,
            verified: bool = False,
            verification_status: str = "",
            metrics_before: dict = None,
            metrics_after: dict = None,
            improvement_detected: bool = False,
            intent_record_id: str = "",
            diagnosis_id: str = "",
            recommendation_id: str = "",
            compliance_id: str = "",
            action_id: str = "",
            execution_id: str = "",
            agent_name: str = "execution",
    ) -> dict:
        """
        Log a result record (after action execution).

        Args:
            action_type:  Type of action executed
            target_node_id: Target node ID
            target_node_name: Target node name
            success: Whether action succeeded
            status:  Execution status
            result_message: Success message
            error_message: Error message if failed
            started_at: When execution started
            completed_at: When execution completed
            duration_ms: Duration in milliseconds
            retry_count: Number of retries
            verified: Whether result was verified
            verification_status: Verification status
            metrics_before:  Metrics before execution
            metrics_after: Metrics after execution
            improvement_detected: Whether improvement was detected
            intent_record_id: Related intent record ID
            diagnosis_id: Related diagnosis ID
            recommendation_id: Related recommendation ID
            compliance_id: Related compliance result ID
            action_id: Action ID
            execution_id:  Execution ID
            agent_name: Name of the agent

        Returns:
            Transaction info
        """
        if not self.log_results:
            return {"enabled": False, "type": "result"}

        record = ResultRecord(
            agent_name=agent_name,
            execution_id=execution_id,
            diagnosis_id=diagnosis_id,
            recommendation_id=recommendation_id,
            compliance_id=compliance_id,
            action_id=action_id,
            intent_record_id=intent_record_id,
            action_type=action_type,
            target_node_id=target_node_id,
            target_node_name=target_node_name,
            success=success,
            status=status,
            result_message=result_message,
            error_message=error_message,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            retry_count=retry_count,
            verified=verified,
            verification_status=verification_status,
            metrics_before=metrics_before or {},
            metrics_after=metrics_after or {},
            improvement_detected=improvement_detected,
            summary=f"Result:  {action_type} on {target_node_id} - {'SUCCESS' if success else 'FAILED'}",
        )

        return self.log_record(record)

    def log_denial(
            self,
            action_type: str,
            target_node_id: str,
            target_node_name: str = "",
            denial_reason: str = "",
            violation_type: str = "",
            rule_id: str = "",
            rule_name: str = "",
            original_issue_type: str = "",
            original_issue_severity: str = "",
            resolution_options: List[str] = None,
            can_override: bool = False,
            override_requires: str = "",
            diagnosis_id: str = "",
            recommendation_id: str = "",
            compliance_id: str = "",
            action_id: str = "",
            agent_name: str = "compliance",
    ) -> dict:
        """
        Log a denial record (compliance rejection).

        Args:
            action_type: Type of action denied
            target_node_id:  Target node ID
            target_node_name: Target node name
            denial_reason:  Why the action was denied
            violation_type: Type of violation
            rule_id: Rule that was violated
            rule_name: Name of the rule
            original_issue_type: Type of issue that triggered this
            original_issue_severity: Severity of the original issue
            resolution_options:  Options to resolve the denial
            can_override: Whether the denial can be overridden
            override_requires: What's needed to override
            diagnosis_id: Related diagnosis ID
            recommendation_id: Related recommendation ID
            compliance_id: Related compliance result ID
            action_id: Action ID
            agent_name: Name of the agent

        Returns:
            Transaction info
        """
        if not self.log_denials:
            return {"enabled": False, "type": "denial"}

        record = DenialRecord(
            agent_name=agent_name,
            diagnosis_id=diagnosis_id,
            recommendation_id=recommendation_id,
            compliance_id=compliance_id,
            action_id=action_id,
            action_type=action_type,
            target_node_id=target_node_id,
            target_node_name=target_node_name,
            denial_reason=denial_reason,
            violation_type=violation_type,
            rule_id=rule_id,
            rule_name=rule_name,
            original_issue_type=original_issue_type,
            original_issue_severity=original_issue_severity,
            resolution_options=resolution_options or [],
            can_override=can_override,
            override_requires=override_requires,
            summary=f"Denial: {action_type} on {target_node_id} - {denial_reason}",
        )

        return self.log_record(record)

    def query(
            self,
            record_type: Optional[AuditRecordType] = None,
            limit: int = 100,
    ) -> List[dict]:
        """
        Query audit records.

        Args:
            record_type: Filter by record type
            limit: Maximum number of results

        Returns:
            List of audit records
        """
        if not self._connected:
            self.connect()

        if record_type:
            prefix = f"audit:{record_type.value}:"
        else:
            prefix = "audit:"

        results = self.client.scan(prefix, limit=limit)

        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x.get("key", ""), reverse=True)

        return results

    def get_intents(self, limit: int = 100) -> List[dict]:
        """Get intent records."""
        return self.query(AuditRecordType.INTENT, limit)

    def get_results(self, limit: int = 100) -> List[dict]:
        """Get result records."""
        return self.query(AuditRecordType.RESULT, limit)

    def get_denials(self, limit: int = 100) -> List[dict]:
        """Get denial records."""
        return self.query(AuditRecordType.DENIAL, limit)

    def get_record(self, key: str, verify: bool = True) -> Optional[dict]:
        """
        Get a specific audit record.

        Args:
            key: Record key
            verify: Whether to verify cryptographically

        Returns:
            The audit record or None
        """
        if not self._connected:
            self.connect()

        if verify:
            return self.client.verified_get(key)
        else:
            value = self.client.get(key)
            if value:
                return {"value": value, "verified": False}
            return None

    def get_stats(self) -> dict:
        """Get audit statistics."""
        if not self._connected:
            self.connect()

        # Count records by type
        intents = len(self.get_intents(limit=1000))
        results = len(self.get_results(limit=1000))
        denials = len(self.get_denials(limit=1000))

        db_stats = self.client.get_stats()

        return {
            "enabled": self.enabled,
            "connected": self._connected,
            "database": db_stats,
            "records": {
                "intents": intents,
                "results": results,
                "denials": denials,
                "total": intents + results + denials,
            },
        }