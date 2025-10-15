import re
import json
import statistics
from typing import List, Dict, Tuple

def parse_ping(raw_output: str) -> Dict:
    """Parse ping output and compute average latency, jitter, packet loss."""
    lines = raw_output.strip().split('\n')

    # Extract RTT values and packet loss info
    rtt_values = []
    packets_sent = 0
    packets_received = 0

    for line in lines:
        if 'time=' in line and 'ms' in line:
            # Extract time value: "time=25ms" or "time<1ms"
            time_match = re.search(r'time[<=](\d+)ms', line)
            if time_match:
                rtt_values.append(int(time_match.group(1)))
            elif 'time<1ms' in line:
                rtt_values.append(1)  # Treat <1ms as 1ms

        # Count packets
        if 'Packets: Sent =' in line:
            packets_sent = int(re.search(r'Sent = (\d+)', line).group(1))
        if 'Packets: Received =' in line:
            packets_received = int(re.search(r'Received = (\d+)', line).group(1))

    # Calculate metrics
    packet_loss = ((packets_sent - packets_received) / packets_sent * 100) if packets_sent > 0 else 0

    if rtt_values:
        average_latency = statistics.mean(rtt_values)
        if len(rtt_values) > 1:
            jitter = statistics.stdev(rtt_values)  # Standard deviation as jitter approximation
        else:
            jitter = 0
    else:
        average_latency = 0
        jitter = 0

    return {
        "average_latency": average_latency,
        "jitter": jitter,
        "packet_loss": packet_loss,
        "packets_sent": packets_sent,
        "packets_received": packets_received,
        "rtt_values": rtt_values
    }

def parse_traceroute(raw_output: str) -> List[Dict]:
    """Parse traceroute output and extract list of hops with RTTs."""
    lines = raw_output.strip().split('\n')
    hops = []

    for line in lines[4:]:  # Skip header lines
        if line.strip() and not line.startswith('Trace complete'):
            parts = line.strip().split()
            if len(parts) >= 3:
                hop_number = int(parts[0])
                ip_address = parts[1]
                # Extract RTT values (there might be multiple)
                rtt_values = []

                for part in parts[2:]:
                    if 'ms' in part:
                        # Extract numeric value from RTT like "25ms" or "<1ms"
                        rtt_match = re.search(r'(\d+)ms', part)
                        if rtt_match:
                            rtt_values.append(int(rtt_match.group(1)))
                        elif '<1ms' in part:
                            rtt_values.append(1)

                if rtt_values:
                    avg_rtt = statistics.mean(rtt_values)
                else:
                    avg_rtt = None

                hops.append({
                    "hop_number": hop_number,
                    "ip_address": ip_address,
                    "rtt_values": rtt_values,
                    "avg_rtt": avg_rtt
                })

    return hops

def parse_iperf(raw_json: str) -> Dict:
    """Parse iperf3 JSON output and extract bandwidth metrics."""
    try:
        data = json.loads(raw_json)

        # Extract bandwidth from bits per second to Mbps
        bandwidth_bps = data.get("end", {}).get("sum_sent", {}).get("bits_per_second", 0)
        bandwidth_mbps = bandwidth_bps / (1000 * 1000)

        # Extract jitter
        jitter_ms = data.get("end", {}).get("sum_sent", {}).get("jitter_ms", 0)

        # Extract packet loss percentage
        packet_loss = data.get("end", {}).get("sum_sent", {}).get("lost_percent", 0)

        return {
            "bandwidth_mbps": bandwidth_mbps,
            "jitter_ms": jitter_ms,
            "packet_loss": packet_loss,
            "bytes_transferred": data.get("end", {}).get("sum_sent", {}).get("bytes", 0),
            "retransmits": data.get("end", {}).get("sum_sent", {}).get("retransmits", 0)
        }

    except json.JSONDecodeError:
        return {
            "error": "Failed to parse iperf JSON output",
            "bandwidth_mbps": 0,
            "jitter_ms": 0,
            "packet_loss": 0,
            "bytes_transferred": 0,
            "retransmits": 0
        }
