import csv
import json
import os
from datetime import datetime
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
    csv_data = {
        "timestamp": datetime.now().isoformat(),
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

# Pydantic Schemas for API requests (no responses needed for CSV storage)
class TraceReq:
    def __init__(self, host: str):
        self.host = host

class IperfReq:
    def __init__(self, server: str, duration: int = 10, protocol: str = "tcp"):
        self.server = server
        self.duration = duration
        self.protocol = protocol
