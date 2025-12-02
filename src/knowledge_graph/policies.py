"""
Policy Manager

Manages policy rules in Neo4j knowledge graph.
"""

from typing import Any, Optional
from datetime import datetime, timezone
from pathlib import Path
import yaml

from src.knowledge_graph.client import Neo4jClient
from src.models.policy import (
    Policy,
    PolicyType,
    PolicyStatus,
    PolicyAction,
    ActionType,
    Condition,
    ConditionOperator,
    PolicyEvaluationResult,
    ComplianceRule,
)
from src.models. network import AnomalyType, AnomalySeverity, NodeType


class PolicyManager:
    """
    Manages policy rules storage and evaluation in Neo4j. 
    
    Example:
        >>> client = Neo4jClient()
        >>> client.connect()
        >>> policy_mgr = PolicyManager(client)
        >>> 
        >>> # Load policies from YAML
        >>> policy_mgr.load_policies_from_yaml("policies/network_policies.yaml")
        >>> 
        >>> # Evaluate policies
        >>> context = {
        ...     "anomaly_type": "HIGH_CPU",
        ...     "severity": "critical",
        ...     "node_type": "router_core",
        ...      "cpu_utilization": 98.5
        ...  }
        >>> results = policy_mgr.evaluate_policies(context)
    """
    
    def __init__(self, client: Neo4jClient):
        """
        Initialize PolicyManager.
        
        Args:
            client: Neo4jClient instance
        """
        self.client = client
    
    # =========================================================================
    # Policy CRUD Operations
    # =========================================================================
    
    def create_policy(self, policy: Policy) -> dict[str, Any]:
        """
        Create a policy in Neo4j. 
        
        Args:
            policy: Policy object to create
        
        Returns:
            Created policy properties
        """
        query = """
        MERGE (p:Policy {id: $id})
        SET p. name = $name,
            p.description = $description,
            p.version = $version,
            p.policy_type = $policy_type,
            p.status = $status,
            p.priority = $priority,
            p.conditions = $conditions,
            p.actions = $actions,
            p.applies_to_node_types = $applies_to_node_types,
            p.applies_to_locations = $applies_to_locations,
            p.active_hours_start = $active_hours_start,
            p.active_hours_end = $active_hours_end,
            p. active_days = $active_days,
            p.created_at = $created_at,
            p.updated_at = datetime(),
            p.created_by = $created_by,
            p.tags = $tags
        RETURN p
        """
        
        # Serialize conditions and actions to JSON strings
        import json
        conditions_json = json.dumps([c.model_dump() for c in policy.conditions])
        actions_json = json.dumps([a.model_dump() for a in policy.actions])
        
        parameters = {
            "id": policy.id,
            "name": policy.name,
            "description": policy. description,
            "version": policy.version,
            "policy_type": policy. policy_type.value,
            "status": policy.status. value,
            "priority": policy.priority,
            "conditions": conditions_json,
            "actions": actions_json,
            "applies_to_node_types": policy.applies_to_node_types,
            "applies_to_locations": policy. applies_to_locations,
            "active_hours_start": policy.active_hours_start,
            "active_hours_end": policy.active_hours_end,
            "active_days": policy.active_days,
            "created_at": policy.created_at.isoformat(),
            "created_by": policy.created_by,
            "tags": policy. tags,
        }
        
        result = self.client. execute_write(query, parameters)
        
        # Create relationships to node types this policy applies to
        if policy.applies_to_node_types:
            for node_type in policy.applies_to_node_types:
                self._create_applies_to_relationship(policy.id, node_type)
        
        return result[0]["p"] if result else {}
    
    def _create_applies_to_relationship(self, policy_id: str, node_type: str) -> None:
        """Create APPLIES_TO relationship between policy and node type."""
        query = """
        MATCH (p:Policy {id: $policy_id})
        MERGE (nt:NodeType {name: $node_type})
        MERGE (p)-[:APPLIES_TO]->(nt)
        """
        self.client.execute_write(query, {
            "policy_id": policy_id,
            "node_type": node_type,
        })
    
    def get_policy(self, policy_id: str) -> Optional[Policy]:
        """
        Get a policy by ID.
        
        Args:
            policy_id: Policy ID
        
        Returns:
            Policy object or None if not found
        """
        query = """
        MATCH (p:Policy {id: $id})
        RETURN p
        """
        
        result = self. client.execute_read(query, {"id": policy_id})
        
        if not result:
            return None
        
        return self._policy_from_record(result[0]["p"])
    
    def get_all_policies(self, status: Optional[PolicyStatus] = None) -> list[Policy]:
        """
        Get all policies, optionally filtered by status.
        
        Args:
            status: Optional status filter
        
        Returns:
            List of Policy objects
        """
        if status:
            query = """
            MATCH (p:Policy {status: $status})
            RETURN p
            ORDER BY p.priority ASC, p.name
            """
            result = self.client. execute_read(query, {"status": status. value})
        else:
            query = """
            MATCH (p:Policy)
            RETURN p
            ORDER BY p.priority ASC, p.name
            """
            result = self.client.execute_read(query)
        
        return [self._policy_from_record(r["p"]) for r in result]
    
    def get_policies_by_type(self, policy_type: PolicyType) -> list[Policy]:
        """Get all policies of a specific type."""
        query = """
        MATCH (p:Policy {policy_type: $type})
        RETURN p
        ORDER BY p.priority ASC
        """
        
        result = self. client.execute_read(query, {"type": policy_type. value})
        return [self._policy_from_record(r["p"]) for r in result]
    
    def get_policies_for_node_type(self, node_type: str) -> list[Policy]:
        """Get all policies that apply to a specific node type."""
        query = """
        MATCH (p:Policy)
        WHERE $node_type IN p.applies_to_node_types
           OR size(p.applies_to_node_types) = 0
        RETURN p
        ORDER BY p.priority ASC
        """
        
        result = self.client.execute_read(query, {"node_type": node_type})
        return [self._policy_from_record(r["p"]) for r in result]
    
    def update_policy_status(self, policy_id: str, status: PolicyStatus) -> bool:
        """Update a policy's status."""
        query = """
        MATCH (p:Policy {id: $id})
        SET p.status = $status, p.updated_at = datetime()
        RETURN p
        """
        
        result = self.client.execute_write(query, {
            "id": policy_id,
            "status": status.value,
        })
        
        return len(result) > 0
    
    def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy."""
        query = """
        MATCH (p:Policy {id: $id})
        DETACH DELETE p
        RETURN count(p) as deleted
        """
        
        result = self.client.execute_write(query, {"id": policy_id})
        return result[0]["deleted"] > 0 if result else False
    
    # =========================================================================
    # Compliance Rules Operations
    # =========================================================================
    
    def create_compliance_rule(self, rule: ComplianceRule) -> dict[str, Any]:
        """Create a compliance rule in Neo4j."""
        query = """
        MERGE (c:ComplianceRule {id: $id})
        SET c.name = $name,
            c.description = $description,
            c.regulation = $regulation,
            c.severity = $severity,
            c.check_type = $check_type,
            c.parameters = $parameters,
            c.enforcement = $enforcement,
            c.created_at = $created_at,
            c. tags = $tags
        RETURN c
        """
        
        import json
        
        parameters = {
            "id": rule.id,
            "name": rule.name,
            "description": rule.description,
            "regulation": rule.regulation,
            "severity": rule. severity,
            "check_type": rule.check_type,
            "parameters": json.dumps(rule.parameters),
            "enforcement": rule. enforcement,
            "created_at": rule.created_at. isoformat(),
            "tags": rule.tags,
        }
        
        result = self.client.execute_write(query, parameters)
        return result[0]["c"] if result else {}
    
    def get_compliance_rules(self, regulation: Optional[str] = None) -> list[ComplianceRule]:
        """Get all compliance rules, optionally filtered by regulation."""
        if regulation:
            query = """
            MATCH (c:ComplianceRule {regulation: $regulation})
            RETURN c
            ORDER BY c.severity DESC, c.name
            """
            result = self.client.execute_read(query, {"regulation": regulation})
        else:
            query = """
            MATCH (c:ComplianceRule)
            RETURN c
            ORDER BY c.regulation, c.name
            """
            result = self.client.execute_read(query)
        
        return [self._compliance_rule_from_record(r["c"]) for r in result]
    
    # =========================================================================
    # Policy Evaluation
    # =========================================================================
    
    def evaluate_policies(
        self,
        context: dict[str, Any],
        node_type: Optional[str] = None,
    ) -> list[PolicyEvaluationResult]:
        """
        Evaluate all applicable policies against a context.
        
        Args:
            context: Dictionary with evaluation context (e.g., anomaly_type, severity, metrics)
            node_type: Optional node type to filter policies
        
        Returns:
            List of PolicyEvaluationResult objects
        """
        # Get applicable policies
        if node_type:
            policies = self. get_policies_for_node_type(node_type)
        else:
            policies = self.get_all_policies(status=PolicyStatus. ACTIVE)
        
        results = []
        now = datetime.now(timezone.utc)
        
        for policy in policies:
            # Check if policy is active at current time
            if not policy.is_active_at(now):
                continue
            
            # Evaluate conditions
            conditions_met = []
            conditions_not_met = []
            
            for condition in policy. conditions:
                if condition.evaluate(context):
                    conditions_met. append(f"{condition.field} {condition.operator. value} {condition. value}")
                else:
                    conditions_not_met. append(f"{condition.field} {condition.operator.value} {condition.value}")
            
            # Policy matches if all conditions are met
            matched = len(conditions_not_met) == 0 and len(policy.conditions) > 0
            
            results.append(PolicyEvaluationResult(
                policy_id=policy.id,
                policy_name=policy.name,
                policy_version=policy.version,
                matched=matched,
                conditions_met=conditions_met,
                conditions_not_met=conditions_not_met,
                recommended_actions=policy.actions if matched else [],
                metadata={
                    "priority": policy.priority,
                    "policy_type": policy. policy_type.value,
                }
            ))
        
        # Sort by match status and priority
        results. sort(key=lambda r: (not r.matched, r.metadata. get("priority", 100)))
        
        return results
    
    def get_matching_policies(
        self,
        context: dict[str, Any],
        node_type: Optional[str] = None,
    ) -> list[Policy]:
        """
        Get policies that match a given context.
        
        Args:
            context: Evaluation context
            node_type: Optional node type filter
        
        Returns:
            List of matching Policy objects
        """
        results = self.evaluate_policies(context, node_type)
        matching_ids = [r.policy_id for r in results if r.matched]
        
        return [p for p in self. get_all_policies() if p.id in matching_ids]
    
    def get_recommended_actions(
        self,
        context: dict[str, Any],
        node_type: Optional[str] = None,
    ) -> list[PolicyAction]:
        """
        Get recommended actions for a given context.
        
        Args:
            context: Evaluation context
            node_type: Optional node type filter
        
        Returns:
            List of PolicyAction objects from matching policies
        """
        results = self.evaluate_policies(context, node_type)
        
        actions = []
        for result in results:
            if result.matched:
                actions. extend(result.recommended_actions)
        
        return actions
    
    # =========================================================================
    # Policy Loading from YAML
    # =========================================================================
    
    def load_policies_from_yaml(self, file_path: str) -> int:
        """
        Load policies from a YAML file. 
        
        Args:
            file_path: Path to YAML file
        
        Returns:
            Number of policies loaded
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Policy file not found: {file_path}")
        
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        
        count = 0
        policies = data.get("policies", [])
        
        for policy_data in policies:
            policy = self._policy_from_yaml(policy_data)
            self.create_policy(policy)
            count += 1
        
        # Load compliance rules if present
        compliance_rules = data.get("compliance_rules", [])
        for rule_data in compliance_rules:
            rule = self._compliance_rule_from_yaml(rule_data)
            self.create_compliance_rule(rule)
        
        return count
    
    def _policy_from_yaml(self, data: dict) -> Policy:
        """Convert YAML data to Policy object."""
        # Parse conditions
        conditions = []
        for cond in data.get("conditions", []):
            conditions.append(Condition(
                field=cond["field"],
                operator=ConditionOperator(cond["operator"]),
                value=cond["value"],
            ))
        
        # Parse actions
        actions = []
        for action in data.get("actions", []):
            actions.append(PolicyAction(
                action_type=ActionType(action["action_type"]),
                target=action. get("target"),
                parameters=action.get("parameters", {}),
                timeout_seconds=action.get("timeout_seconds", 300),
                retry_count=action. get("retry_count", 0),
                requires_approval=action.get("requires_approval", False),
            ))
        
        return Policy(
            id=data. get("id", f"POL-{data['name'][:8]. upper()}"),
            name=data["name"],
            description=data.get("description", ""),
            version=data. get("version", "1. 0. 0"),
            policy_type=PolicyType(data. get("policy_type", "remediation")),
            status=PolicyStatus(data.get("status", "active")),
            priority=data.get("priority", 100),
            conditions=conditions,
            actions=actions,
            applies_to_node_types=data.get("applies_to_node_types", []),
            applies_to_locations=data.get("applies_to_locations", []),
            active_hours_start=data.get("active_hours_start"),
            active_hours_end=data. get("active_hours_end"),
            active_days=data.get("active_days", [0, 1, 2, 3, 4, 5, 6]),
            tags=data.get("tags", []),
        )
    
    def _compliance_rule_from_yaml(self, data: dict) -> ComplianceRule:
        """Convert YAML data to ComplianceRule object."""
        return ComplianceRule(
            id=data.get("id", f"COMP-{data['name'][:8].upper()}"),
            name=data["name"],
            description=data.get("description", ""),
            regulation=data["regulation"],
            severity=data.get("severity", "medium"),
            check_type=data["check_type"],
            parameters=data. get("parameters", {}),
            enforcement=data.get("enforcement", "block"),
            tags=data.get("tags", []),
        )
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _policy_from_record(self, record: dict) -> Policy:
        """Convert a Neo4j record to Policy object."""
        import json
        
        # Parse conditions and actions from JSON
        conditions = []
        try:
            conditions_data = json.loads(record. get("conditions", "[]"))
            conditions = [Condition(**c) for c in conditions_data]
        except (json.JSONDecodeError, TypeError):
            pass
        
        actions = []
        try:
            actions_data = json.loads(record.get("actions", "[]"))
            actions = [PolicyAction(**a) for a in actions_data]
        except (json.JSONDecodeError, TypeError):
            pass
        
        return Policy(
            id=record.get("id", ""),
            name=record.get("name", ""),
            description=record.get("description", ""),
            version=record. get("version", "1.0.0"),
            policy_type=PolicyType(record.get("policy_type", "remediation")),
            status=PolicyStatus(record.get("status", "active")),
            priority=record.get("priority", 100),
            conditions=conditions,
            actions=actions,
            applies_to_node_types=record.get("applies_to_node_types", []),
            applies_to_locations=record.get("applies_to_locations", []),
            active_hours_start=record.get("active_hours_start"),
            active_hours_end=record.get("active_hours_end"),
            active_days=record.get("active_days", [0, 1, 2, 3, 4, 5, 6]),
            tags=record.get("tags", []),
        )
    
    def _compliance_rule_from_record(self, record: dict) -> ComplianceRule:
        """Convert a Neo4j record to ComplianceRule object."""
        import json
        
        parameters = {}
        try:
            parameters = json.loads(record.get("parameters", "{}"))
        except (json.JSONDecodeError, TypeError):
            pass
        
        return ComplianceRule(
            id=record. get("id", ""),
            name=record.get("name", ""),
            description=record.get("description", ""),
            regulation=record.get("regulation", ""),
            severity=record.get("severity", "medium"),
            check_type=record.get("check_type", ""),
            parameters=parameters,
            enforcement=record.get("enforcement", "block"),
            tags=record. get("tags", []),
        )
    
    def get_policy_summary(self) -> dict[str, Any]:
        """Get summary of policies in the database."""
        query = """
        MATCH (p:Policy)
        RETURN count(p) as total,
               count(CASE WHEN p.status = 'active' THEN 1 END) as active,
               collect(DISTINCT p. policy_type) as types
        """
        
        result = self. client.execute_read(query)
        
        if not result:
            return {"total": 0, "active": 0, "types": []}
        
        r = result[0]
        return {
            "total": r["total"],
            "active": r["active"],
            "types": r["types"],
        }