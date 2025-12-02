"""
Network data models using Pydantic for type safety and validation.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid


# ============================================================================
# Enums
# ============================================================================

class NodeType(str, Enum):
    """Types of network nodes."""
    ROUTER_CORE = "router_core"
    ROUTER_EDGE = "router_edge"
    SWITCH_DISTRIBUTION = "switch_distribution"
    SWITCH_ACCESS = "switch_access"
    SERVER = "server"
    FIREWALL = "firewall"
    LOAD_BALANCER = "load_balancer"


class NodeStatus(str, Enum):
    """Operational status of a network node."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DOWN = "down"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class LogLevel(str, Enum):
    """Log severity levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class MetricType(str, Enum):
    """Types of telemetry metrics."""
    CPU_UTILIZATION = "cpu_utilization"
    MEMORY_UTILIZATION = "memory_utilization"
    BANDWIDTH_IN = "bandwidth_in"
    BANDWIDTH_OUT = "bandwidth_out"
    PACKET_LOSS = "packet_loss"
    LATENCY = "latency"
    ERROR_COUNT = "error_count"
    TEMPERATURE = "temperature"
    UPTIME = "uptime"
    INTERFACE_STATUS = "interface_status"


class AnomalyType(str, Enum):
    """Types of anomalies that can be injected."""
    HIGH_CPU = "HIGH_CPU"
    MEMORY_LEAK = "MEMORY_LEAK"
    INTERFACE_DOWN = "INTERFACE_DOWN"
    PACKET_LOSS = "PACKET_LOSS"
    HIGH_LATENCY = "HIGH_LATENCY"
    AUTH_FAILURE = "AUTH_FAILURE"
    CONFIG_DRIFT = "CONFIG_DRIFT"
    SERVICE_DEGRADATION = "SERVICE_DEGRADATION"
    DISK_FULL = "DISK_FULL"
    TEMPERATURE_HIGH = "TEMPERATURE_HIGH"


class AnomalySeverity(str, Enum):
    """Severity levels for anomalies."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================================
# Network Models
# ============================================================================

class Node(BaseModel):
    """Represents a network node (router, switch, server, etc.)."""
    
    id: str = Field(... , description="Unique identifier for the node")
    name: str = Field(... , description="Human-readable name")
    type: NodeType = Field(..., description="Type of network device")
    ip_address: str = Field(..., description="Management IP address")
    location: str = Field(default="datacenter-1", description="Physical location")
    status: NodeStatus = Field(default=NodeStatus.HEALTHY, description="Current status")
    vendor: str = Field(default="Generic", description="Equipment vendor")
    model: str = Field(default="Unknown", description="Equipment model")
    interfaces: list[str] = Field(default_factory=list, description="Network interfaces")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def __hash__(self):
        return hash(self.id)


class Link(BaseModel):
    """Represents a connection between two network nodes."""
    
    id: str = Field(default_factory=lambda: str(uuid. uuid4())[:8])
    source_node_id: str = Field(..., description="Source node ID")
    target_node_id: str = Field(... , description="Target node ID")
    source_interface: str = Field(default="eth0", description="Source interface")
    target_interface: str = Field(default="eth0", description="Target interface")
    bandwidth_mbps: int = Field(default=1000, description="Link bandwidth in Mbps")
    latency_ms: float = Field(default=1.0, description="Link latency in milliseconds")
    status: str = Field(default="up", description="Link status (up/down)")
    metadata: dict[str, Any] = Field(default_factory=dict)


class NetworkTopology(BaseModel):
    """Represents the entire network topology."""
    
    id: str = Field(default_factory=lambda: str(uuid. uuid4())[:8])
    name: str = Field(default="telco-network", description="Topology name")
    nodes: dict[str, Node] = Field(default_factory=dict, description="All nodes by ID")
    links: list[Link] = Field(default_factory=list, description="All links")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        return self. nodes.get(node_id)
    
    def get_connected_nodes(self, node_id: str) -> list[Node]:
        """Get all nodes connected to the given node."""
        connected_ids = set()
        for link in self. links:
            if link.source_node_id == node_id:
                connected_ids.add(link. target_node_id)
            elif link.target_node_id == node_id:
                connected_ids.add(link.source_node_id)
        return [self.nodes[nid] for nid in connected_ids if nid in self. nodes]
    
    def get_all_nodes(self) -> list[Node]:
        """Get all nodes in the topology."""
        return list(self.nodes.values())


# ============================================================================
# Log Models
# ============================================================================

class LogEntry(BaseModel):
    """Represents a single log entry from a network device."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    node_id: str = Field(..., description="Source node ID")
    node_name: str = Field(..., description="Source node name")
    level: LogLevel = Field(... , description="Log severity level")
    source: str = Field(..., description="Log source (e.g., 'system', 'interface', 'security')")
    message: str = Field(... , description="Log message")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    
    def to_syslog_format(self) -> str:
        """Convert to syslog-style format."""
        return f"{self.timestamp.isoformat()} {self.node_name} {self.source}[{self.level. value}]: {self.message}"


# ============================================================================
# Telemetry Models
# ============================================================================

class MetricReading(BaseModel):
    """A single metric reading."""
    
    id: str = Field(default_factory=lambda: str(uuid. uuid4())[:8])
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    node_id: str = Field(..., description="Source node ID")
    metric_type: MetricType = Field(..., description="Type of metric")
    value: float = Field(..., description="Metric value")
    unit: str = Field(..., description="Unit of measurement")
    oid: Optional[str] = Field(default=None, description="SNMP OID reference")
    metadata: dict[str, Any] = Field(default_factory=dict)


class TelemetrySnapshot(BaseModel):
    """A complete telemetry snapshot for a node."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    node_id: str = Field(..., description="Source node ID")
    node_name: str = Field(..., description="Source node name")
    metrics: list[MetricReading] = Field(default_factory=list)
    status: NodeStatus = Field(default=NodeStatus.HEALTHY)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def get_metric(self, metric_type: MetricType) -> Optional[MetricReading]:
        """Get a specific metric from the snapshot."""
        for metric in self. metrics:
            if metric.metric_type == metric_type:
                return metric
        return None


# ============================================================================
# Anomaly Models
# ============================================================================

class Anomaly(BaseModel):
    """Represents an injected or detected anomaly."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    anomaly_type: AnomalyType = Field(..., description="Type of anomaly")
    severity: AnomalySeverity = Field(default=AnomalySeverity. MEDIUM)
    node_id: str = Field(... , description="Affected node ID")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    duration_seconds: Optional[int] = Field(default=None, description="Duration in seconds")
    ended_at: Optional[datetime] = Field(default=None)
    is_active: bool = Field(default=True)
    description: str = Field(default="", description="Human-readable description")
    affected_metrics: list[MetricType] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def end(self) -> None:
        """Mark the anomaly as ended."""
        self.is_active = False
        self.ended_at = datetime.utcnow()