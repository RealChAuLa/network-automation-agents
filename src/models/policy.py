"""
Policy data models for the network automation system.
"""

from datetime import timezone
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid


class PolicyType(str, Enum):
    """Types of policies."""
    REMEDIATION = "remediation"          # Auto-fix issues
    ESCALATION = "escalation"            # Escalate to humans
    PREVENTION = "prevention"            # Prevent actions
    COMPLIANCE = "compliance"            # Regulatory compliance
    MAINTENANCE = "maintenance"          # Maintenance windows


class PolicyStatus(str, Enum):
    """Policy status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"
    DEPRECATED = "deprecated"


class ActionType(str, Enum):
    """Types of actions that can be taken."""
    RESTART_SERVICE = "restart_service"
    RESTART_NODE = "restart_node"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    FAILOVER = "failover"
    BLOCK_TRAFFIC = "block_traffic"
    RATE_LIMIT = "rate_limit"
    UPDATE_CONFIG = "update_config"
    CLEAR_CACHE = "clear_cache"
    NOTIFY = "notify"
    LOG_ONLY = "log_only"
    ESCALATE = "escalate"


class ConditionOperator(str, Enum):
    """Operators for policy conditions."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IN = "in"
    NOT_IN = "not_in"
    REGEX = "regex"


class Condition(BaseModel):
    """A single condition in a policy rule."""
    
    field: str = Field(... , description="Field to evaluate (e.g., 'anomaly_type', 'severity', 'node_type')")
    operator: ConditionOperator = Field(..., description="Comparison operator")
    value: Any = Field(... , description="Value to compare against")
    
    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate this condition against a context."""
        field_value = context. get(self.field)
        
        if field_value is None:
            return False
        
        if self.operator == ConditionOperator. EQUALS:
            return field_value == self.value
        elif self.operator == ConditionOperator.NOT_EQUALS:
            return field_value != self. value
        elif self.operator == ConditionOperator. GREATER_THAN:
            return field_value > self.value
        elif self. operator == ConditionOperator.LESS_THAN:
            return field_value < self.value
        elif self.operator == ConditionOperator.GREATER_THAN_OR_EQUAL:
            return field_value >= self.value
        elif self.operator == ConditionOperator.LESS_THAN_OR_EQUAL:
            return field_value <= self.value
        elif self.operator == ConditionOperator. CONTAINS:
            return self. value in field_value
        elif self. operator == ConditionOperator.NOT_CONTAINS:
            return self.value not in field_value
        elif self.operator == ConditionOperator.IN:
            return field_value in self.value
        elif self.operator == ConditionOperator.NOT_IN:
            return field_value not in self.value
        elif self.operator == ConditionOperator. REGEX:
            import re
            return bool(re.match(self.value, str(field_value)))
        
        return False


class PolicyAction(BaseModel):
    """An action to be taken when policy conditions are met."""
    
    action_type: ActionType = Field(..., description="Type of action")
    target: Optional[str] = Field(default=None, description="Target of the action (e.g., service name)")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    timeout_seconds: int = Field(default=300, description="Action timeout")
    retry_count: int = Field(default=0, description="Number of retries on failure")
    requires_approval: bool = Field(default=False, description="Whether action requires additional approval")


class Policy(BaseModel):
    """A policy rule that defines when and what actions to take."""
    
    id: str = Field(default_factory=lambda: f"POL-{str(uuid.uuid4())[:8]. upper()}")
    name: str = Field(... , description="Human-readable policy name")
    description: str = Field(default="", description="Policy description")
    version: str = Field(default="1.0. 0", description="Policy version")
    policy_type: PolicyType = Field(..., description="Type of policy")
    status: PolicyStatus = Field(default=PolicyStatus. ACTIVE)
    priority: int = Field(default=100, description="Priority (lower = higher priority)")
    
    # Conditions - ALL must be true for policy to apply (AND logic)
    conditions: list[Condition] = Field(default_factory=list)
    
    # Actions to take when conditions are met
    actions: list[PolicyAction] = Field(default_factory=list)
    
    # Scope - what this policy applies to
    applies_to_node_types: list[str] = Field(default_factory=list, description="Node types this applies to (empty = all)")
    applies_to_locations: list[str] = Field(default_factory=list, description="Locations this applies to (empty = all)")
    
    # Time constraints
    active_hours_start: Optional[int] = Field(default=None, description="Start hour (0-23)")
    active_hours_end: Optional[int] = Field(default=None, description="End hour (0-23)")
    active_days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6], description="Active days (0=Monday)")
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default="system")
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def evaluate_conditions(self, context: dict[str, Any]) -> bool:
        """Evaluate all conditions against a context."""
        if not self.conditions:
            return True
        return all(condition.evaluate(context) for condition in self. conditions)
    
    def is_active_at(self, dt: datetime) -> bool:
        """Check if policy is active at a given datetime."""
        if self.status != PolicyStatus. ACTIVE:
            return False
        
        # Check day of week
        if dt.weekday() not in self.active_days:
            return False
        
        # Check hours
        if self. active_hours_start is not None and self.active_hours_end is not None:
            if not (self.active_hours_start <= dt.hour < self.active_hours_end):
                return False
        
        return True
    
    def applies_to_node(self, node_type: str, location: str) -> bool:
        """Check if policy applies to a specific node."""
        # Check node type
        if self. applies_to_node_types and node_type not in self. applies_to_node_types:
            return False
        
        # Check location
        if self.applies_to_locations and location not in self. applies_to_locations:
            return False
        
        return True


class PolicyEvaluationResult(BaseModel):
    """Result of evaluating a policy against a context."""
    
    policy_id: str
    policy_name: str
    policy_version: str
    matched: bool
    conditions_met: list[str] = Field(default_factory=list)
    conditions_not_met: list[str] = Field(default_factory=list)
    recommended_actions: list[PolicyAction] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComplianceRule(BaseModel):
    """A compliance rule for regulatory requirements."""
    
    id: str = Field(default_factory=lambda: f"COMP-{str(uuid.uuid4())[:8].upper()}")
    name: str = Field(..., description="Rule name")
    description: str = Field(default="")
    regulation: str = Field(... , description="Regulation this implements (e.g., 'SOC2', 'GDPR', 'PCI-DSS')")
    severity: str = Field(default="medium", description="Severity if violated")
    
    # What this rule checks
    check_type: str = Field(... , description="Type of check (e.g., 'maintenance_window', 'approval_required')")
    parameters: dict[str, Any] = Field(default_factory=dict)
    
    # Enforcement
    enforcement: str = Field(default="block", description="What to do on violation: 'block', 'warn', 'log'")
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = Field(default_factory=list)