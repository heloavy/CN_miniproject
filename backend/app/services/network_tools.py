import asyncio
import subprocess
import platform
import re
import json
from typing import List, Dict, Tuple
import time

class NetworkTools:
    def __init__(self):
        if platform.system() != "Windows":
            raise Exception("This application is designed for Windows only")

    async def run_ping(self, host: str, interval: int = 1) -> str:
        """Run Windows ping command and return raw output."""
        try:
            process = await asyncio.create_subprocess_exec(
                "ping", "-t", host,  # -t for continuous ping
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                text=True
            )

            # Read output in real-time
            output_lines = []
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                output_lines.append(line.strip())
                if len(output_lines) > 100:  # Limit buffer
                    output_lines = output_lines[-50:]

            await process.terminate()
            return "\n".join(output_lines)

        except Exception as e:
            return f"Error running ping: {str(e)}"

    async def run_traceroute(self, host: str) -> str:
        """Run Windows tracert command and return raw output."""
        try:
            process = await asyncio.create_subprocess_exec(
                "tracert", host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                text=True
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return stdout
            else:
                return f"Error: {stderr}"

        except FileNotFoundError:
            return "Error: tracert command not found in PATH"
        except Exception as e:
            return f"Error running tracert: {str(e)}"

    async def run_iperf(self, server: str, duration: int = 10, protocol: str = "TCP") -> str:
        """Run iperf3 command and return raw JSON output."""
        try:
            if protocol.upper() == "UDP":
                cmd = ["iperf3", "-c", server, "-u", "-t", str(duration), "-J"]
            else:
                cmd = ["iperf3", "-c", server, "-t", str(duration), "-J"]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                text=True
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return stdout
            else:
                return f"Error: {stderr}"

        except FileNotFoundError:
            return "Error: iperf3 command not found in PATH. Please install iperf3 and ensure it's in your PATH."
        except Exception as e:
            return f"Error running iperf3: {str(e)}"

# Parser functions for extracting metrics
def parse_ping_output(raw_output: str) -> Dict:
    """Parse ping output for real-time metrics."""
    lines = raw_output.strip().split('\n')
    rtt_values = []
    packets_sent = 0
    packets_received = 0

    for line in lines:
        if 'time=' in line and 'ms' in line:
            time_match = re.search(r'time[<=](\d+)ms', line)
            if time_match:
                rtt_values.append(int(time_match.group(1)))
            elif 'time<1ms' in line:
                rtt_values.append(1)

        # Count packets
        if 'Packets: Sent =' in line:
            packets_sent = int(re.search(r'Sent = (\d+)', line).group(1))
        if 'Packets: Received =' in line:
            packets_received = int(re.search(r'Received = (\d+)', line).group(1))

    # Calculate metrics
    packet_loss = ((packets_sent - packets_received) / packets_sent * 100) if packets_sent > 0 else 0

    if rtt_values:
        average_latency = sum(rtt_values) / len(rtt_values)
        if len(rtt_values) > 1:
            jitter = max(rtt_values) - min(rtt_values)  # Simple jitter calculation
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

def parse_traceroute_output(raw_output: str) -> List[Dict]:
    """Parse traceroute output and extract hops."""
    lines = raw_output.strip().split('\n')
    hops = []

    for line in lines[4:]:  # Skip header lines
        if line.strip() and not line.startswith('Trace complete'):
            parts = line.strip().split()
            if len(parts) >= 3:
                hop_number = int(parts[0])
                ip_address = parts[1]
                # Extract RTT values
                rtt_values = []
                for part in parts[2:]:
                    if 'ms' in part:
                        rtt_match = re.search(r'(\d+)ms', part)
                        if rtt_match:
                            rtt_values.append(int(rtt_match.group(1)))
                        elif '<1ms' in part:
                            rtt_values.append(1)

                avg_rtt = sum(rtt_values) / len(rtt_values) if rtt_values else None

                hops.append({
                    "hop": hop_number,
                    "ip": ip_address,
                    "rtt_ms": avg_rtt
                })

    return hops

def parse_iperf_output(raw_json: str) -> Dict:
    """Parse iperf3 JSON output."""
    try:
        data = json.loads(raw_json)

        # Extract bandwidth
        bandwidth_bps = data.get("end", {}).get("sum_sent", {}).get("bits_per_second", 0)
        bandwidth_mbps = bandwidth_bps / (1000 * 1000)

        # Extract jitter
        jitter_ms = data.get("end", {}).get("sum_sent", {}).get("jitter_ms", 0)

        # Extract packet loss
        packet_loss = data.get("end", {}).get("sum_sent", {}).get("lost_percent", 0)

        return {
            "bandwidth_mbps": bandwidth_mbps,
            "jitter_ms": jitter_ms,
            "packet_loss": packet_loss,
            "protocol": data.get("start", {}).get("test_start", {}).get("protocol", "TCP")
        }

    except json.JSONDecodeError:
        return {
            "error": "Failed to parse iperf JSON output",
            "bandwidth_mbps": 0,
            "jitter_ms": 0,
            "packet_loss": 0
        }
