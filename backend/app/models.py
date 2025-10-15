import csv
import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any
from pathlib import Path

# CSV Storage System
DATA_DIR = Path("data")
CSV_FILES = {
    "ping": DATA_DIR / "ping_results.csv",
    "traceroute": DATA_DIR / "traceroute_results.csv",
    "iperf": DATA_DIR / "iperf_results.csv"
}

# Create data directory if it doesn't exist
DATA_DIR.mkdir(exist_ok=True)

def save_to_csv(tool: str, data: Dict[str, Any]):
    """Save data to CSV file for the specified tool."""
    file_path = CSV_FILES.get(tool)
    if not file_path:
        raise ValueError(f"Unknown tool: {tool}")

    # Prepare data for CSV
    # Use UTC ISO timestamps to avoid local timezone confusion
    csv_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": json.dumps(data)
    }

    # Check if file exists to determine if we need headers
    file_exists = file_path.exists()

    with open(file_path, 'a', newline='', encoding='utf-8') as csvfile:
        fieldnames = ["timestamp", "data"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow(csv_data)

def load_from_csv(tool: str, target: str = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Load data from CSV file for the specified tool."""
    file_path = CSV_FILES.get(tool)
    if not file_path or not file_path.exists():
        return []

    results = []
    with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        # Use a counter to assign stable, unique IDs that include the tool name
        # and the row index so entries from different tools or reloads won't collide.
        for i, row in enumerate(reader, start=1):
            try:
                data = json.loads(row["data"])
                # Filter by target if specified
                if target and data.get("target") != target and data.get("server") != target:
                    continue
                # Compose a unique string id combining tool, index and timestamp
                unique_id = f"{tool}-{i}-{row.get('timestamp', '')}"
                results.append({
                    "id": unique_id,
                    "timestamp": row["timestamp"],
                    **data
                })
            except json.JSONDecodeError:
                continue  # Skip invalid JSON rows

    # Return most recent results first, limited by limit
    return sorted(results, key=lambda x: x["timestamp"], reverse=True)[:limit]

import csv
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from enum import Enum

# CSV Storage System
DATA_DIR = Path("data")
CSV_FILES = {
    "ping": DATA_DIR / "ping_results.csv",
    "traceroute": DATA_DIR / "traceroute_results.csv",
    "iperf": DATA_DIR / "iperf_results.csv",
    "measurements": DATA_DIR / "measurements.csv",  # For storing enhanced measurement data
    "simulation_scenarios": DATA_DIR / "simulation_scenarios.csv",
}

# Create data directory if it doesn't exist
DATA_DIR.mkdir(exist_ok=True)

def save_to_csv(tool: str, data: Dict[str, Any]):
    """Save data to CSV file for the specified tool."""
    file_path = CSV_FILES.get(tool)
    if not file_path:
        raise ValueError(f"Unknown tool: {tool}")

    # Prepare data for CSV
    # Use UTC ISO timestamps to avoid local timezone confusion
    csv_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": json.dumps(data)
    }

    # Check if file exists to determine if we need headers
    file_exists = file_path.exists()

    with open(file_path, 'a', newline='', encoding='utf-8') as csvfile:
        fieldnames = ["timestamp", "data"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow(csv_data)

def load_from_csv(tool: str, target: str = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Load data from CSV file for the specified tool."""
    file_path = CSV_FILES.get(tool)
    if not file_path or not file_path.exists():
        return []

    results = []
    with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                data = json.loads(row["data"])
                # Filter by target if specified
                if target and data.get("target") != target and data.get("server") != target:
                    continue
                results.append({
                    "id": len(results) + 1,
                    "timestamp": row["timestamp"],
                    **data
                })
            except json.JSONDecodeError:
                continue  # Skip invalid JSON rows

    # Return most recent results first, limited by limit
    return sorted(results, key=lambda x: x["timestamp"], reverse=True)[:limit]

# Enums for type safety
class DeviceType(str, Enum):
    LAPTOP = "laptop"
    PC = "pc"
    SERVER = "server"
    ROUTER = "router"

class DeviceRole(str, Enum):
    ROUTER = "router"
    SERVER = "server"
    PC = "pc"
    WORKSTATION = "workstation"
    SWITCH = "switch"
    FIREWALL = "firewall"
    LOAD_BALANCER = "load-balancer"

class ConnectionType(str, Enum):
    CAT5E = "cat5e"
    CAT6 = "cat6"
    FIBER = "fiber"
    WIRELESS = "wireless"
    SATELLITE = "satellite"
    VPN = "vpn"

class ConnectivityStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

class FaultProfile(str, Enum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    PEAK = "peak"
    FAILURE = "failure"

# Enhanced data models for the network workbench
class SLAThresholds(BaseModel):
    latency_ms: float = Field(..., description="Maximum acceptable latency in milliseconds", gt=0)
    loss_pct: float = Field(..., description="Maximum acceptable packet loss percentage", ge=0, le=100)
    jitter_ms: float = Field(..., description="Maximum acceptable jitter in milliseconds", ge=0)
    throughput_mbps: float = Field(..., description="Minimum acceptable throughput in Mbps", gt=0)

class EdgeSimulation(BaseModel):
    delay_ms: float = Field(..., description="Simulated delay in milliseconds", ge=0)
    loss_pct: float = Field(..., description="Simulated packet loss percentage", ge=0, le=100)
    jitter_ms: float = Field(..., description="Simulated jitter in milliseconds", ge=0)
    capacity_mbps: float = Field(..., description="Link capacity in Mbps", gt=0)

class EdgeMeasurement(BaseModel):
    measured_rtt_ms: Optional[float] = Field(None, description="Latest measured RTT delta for this edge segment")
    last_updated: Optional[str] = Field(None, description="ISO timestamp of last measurement")

class NodeMeasurement(BaseModel):
    last_ping: Optional[float] = Field(None, description="Timestamp of last ping")
    last_traceroute: Optional[float] = Field(None, description="Timestamp of last traceroute")
    last_iperf: Optional[float] = Field(None, description="Timestamp of last iPerf test")
    status: ConnectivityStatus = Field(ConnectivityStatus.UNKNOWN, description="Current connectivity status")

class NodeData(BaseModel):
    label: str = Field(..., description="Display label for the node")
    ip: str = Field(..., description="IP address or hostname")
    type: DeviceType = Field(..., description="Hardware type of the device")
    role: DeviceRole = Field(..., description="Functional role of the device")
    tags: List[str] = Field(default_factory=list, description="Array of tags for categorization and filtering")
    sla_thresholds: SLAThresholds = Field(..., description="SLA thresholds for this node")
    is_iperf_server: bool = Field(False, description="Whether this node can act as an iPerf server")
    measured: Optional[NodeMeasurement] = Field(None, description="Measurement status and timestamps")

class EdgeData(BaseModel):
    type: ConnectionType = Field(..., description="Physical connection type")
    latency: float = Field(..., description="Legacy latency field for backward compatibility", ge=0)
    simulation: EdgeSimulation = Field(..., description="Simulation properties for this edge")
    measurement: EdgeMeasurement = Field(default_factory=EdgeMeasurement, description="Measured overlay data")
    length: Optional[float] = Field(None, description="Physical/virtual length for visualization", ge=0)
    cost: Optional[float] = Field(None, description="Cost metric for path calculation", ge=0)

class TracerouteHop(BaseModel):
    hop: int = Field(..., description="Hop number in the traceroute")
    rtt1: str = Field(..., description="First RTT measurement")
    rtt2: str = Field(..., description="Second RTT measurement")
    rtt3: str = Field(..., description="Third RTT measurement")
    ip: str = Field(..., description="IP address of this hop")
    hostname: Optional[str] = Field(None, description="Hostname if resolved")

class PingResult(BaseModel):
    timestamp: float = Field(..., description="Unix timestamp of the ping")
    latency: Optional[float] = Field(None, description="Latency in milliseconds")
    target: str = Field(..., description="Target IP or hostname")

class TracerouteResult(BaseModel):
    timestamp: float = Field(..., description="Unix timestamp of the traceroute")
    target: str = Field(..., description="Target IP or hostname")
    hops: List[TracerouteHop] = Field(..., description="List of hops in the traceroute")

class IperfResult(BaseModel):
    timestamp: float = Field(..., description="Unix timestamp of the iPerf test")
    target: str = Field(..., description="Target server IP or hostname")
    interval: str = Field(..., description="Time interval")
    transfer: float = Field(..., description="Data transfer amount")
    bitrate: float = Field(..., description="Bitrate in Mbps")

class NetworkPath(BaseModel):
    nodes: List[str] = Field(..., description="Node IDs in path order")
    edges: List[str] = Field(..., description="Edge IDs in path order")
    total_delay_ms: float = Field(..., description="Sum of all edge delays")
    total_jitter_ms: float = Field(..., description="Square root of sum of jitter variances")
    total_loss_pct: float = Field(..., description="1 - product of (1 - loss_pct) for all edges")
    bottleneck_mbps: float = Field(..., description="Minimum capacity along the path")

class SimulationScenario(BaseModel):
    id: str = Field(..., description="Unique identifier for the scenario")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Description of the scenario")
    edge_modifications: Dict[str, Dict[str, float]] = Field(..., description="Edge ID -> simulation modifications")
    is_active: bool = Field(False, description="Whether this scenario is currently active")

class MeasurementOverlay(BaseModel):
    traceroute_path: List[TracerouteHop] = Field(..., description="Full traceroute path")
    matched_edges: List[Dict[str, Any]] = Field(..., description="Edges that matched traceroute hops")
    unmatched_hops: List[Dict[str, Any]] = Field(..., description="Hops that couldn't be matched to edges")

class BulkPingResult(BaseModel):
    node_id: str = Field(..., description="ID of the node that was pinged")
    node_label: str = Field(..., description="Label of the node")
    target_ip: str = Field(..., description="IP address that was pinged")
    latency_ms: Optional[float] = Field(None, description="Measured latency")
    success: bool = Field(..., description="Whether the ping was successful")
    timestamp: float = Field(..., description="Unix timestamp of the measurement")
    error: Optional[str] = Field(None, description="Error message if ping failed")

class PeriodicCheckConfig(BaseModel):
    node_id: str = Field(..., description="ID of the node to check")
    interval_minutes: int = Field(..., description="Check interval in minutes", gt=0)
    enabled: bool = Field(True, description="Whether periodic checks are enabled")
    last_check: Optional[float] = Field(None, description="Unix timestamp of last check")
    next_check: Optional[float] = Field(None, description="Unix timestamp of next scheduled check")

class MeasurementHistory(BaseModel):
    tool: str = Field(..., description="Tool type: ping, traceroute, or iperf")
    target: str = Field(..., description="Target host or server")
    timestamp: float = Field(..., description="Unix timestamp of measurement")
    result: Dict[str, Any] = Field(..., description="Measurement result data")

class SLABreach(BaseModel):
    node_id: str = Field(..., description="ID of the node that breached SLA")
    metric: str = Field(..., description="Which SLA metric was breached")
    measured_value: float = Field(..., description="The measured value that caused the breach")
    threshold_value: float = Field(..., description="The SLA threshold value")
    breach_start: float = Field(..., description="Unix timestamp when breach started")
    breach_end: Optional[float] = Field(None, description="Unix timestamp when breach ended")
    duration_minutes: Optional[float] = Field(None, description="Duration of breach in minutes")

class RouteChange(BaseModel):
    node_id: str = Field(..., description="ID of the node whose route changed")
    timestamp: float = Field(..., description="Unix timestamp of the change")
    previous_hops: List[str] = Field(..., description="Previous hop IP addresses")
    current_hops: List[str] = Field(..., description="Current hop IP addresses")
    change_type: str = Field(..., description="Type of change detected")
    affected_edges: List[str] = Field(..., description="Edges affected by this route change")

# API Request/Response models
class TraceReq(BaseModel):
    host: str = Field(..., description="Target hostname or IP address")

class IperfReq(BaseModel):
    server: str = Field(..., description="iPerf server hostname or IP")
    duration: int = Field(10, description="Test duration in seconds", gt=0)
    protocol: str = Field("tcp", description="Protocol to use (tcp or udp)")

class PingReq(BaseModel):
    host: str = Field(..., description="Target hostname or IP address")
    interval: int = Field(1000, description="Ping interval in milliseconds", gt=0)

class BulkPingReq(BaseModel):
    node_ids: List[str] = Field(..., description="List of node IDs to ping")
    rate_limit_ms: int = Field(100, description="Rate limit between pings in milliseconds", gt=0)

class NodeActionReq(BaseModel):
    node_id: str = Field(..., description="ID of the node to perform action on")
    action: str = Field(..., description="Action to perform: ping, traceroute, or iperf")

class SimulationScenarioReq(BaseModel):
    name: str = Field(..., description="Name for the new scenario")
    description: str = Field("", description="Description of the scenario")
    edge_modifications: Dict[str, Dict[str, float]] = Field(..., description="Edge modifications for this scenario")

# Legacy request models (keeping for backward compatibility)
class LegacyTraceReq:
    def __init__(self, host: str):
        self.host = host

class LegacyIperfReq:
    def __init__(self, server: str, duration: int = 10, protocol: str = "tcp"):
        self.server = server
        self.duration = duration
        self.protocol = protocol
