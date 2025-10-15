import subprocess
import json
import matplotlib.pyplot as plt
import sys

def run_iperf(server, duration=10, protocol='TCP'):
    """Run iperf3 command and return parsed JSON."""
    if protocol.upper() == 'UDP':
        cmd = ["iperf3", "-c", server, "-u", "-t", str(duration), "-J"]
    else:
        cmd = ["iperf3", "-c", server, "-t", str(duration), "-J"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        intervals = data.get("intervals", [])
        bitrates = []
        for interval in intervals:
            for stream in interval.get("streams", []):
                bitrate = stream.get("bits_per_second", 0) / (1000 * 1000)  # Mbps
                bitrates.append(bitrate)
        return bitrates, data.get("end", {}).get("sum_sent", {}).get("bits_per_second", 0) / (1000 * 1000)
    except subprocess.CalledProcessError as e:
        print(f"iPerf failed: {e}")
        return [], 0
    except json.JSONDecodeError:
        print("Failed to parse iperf JSON.")
        return [], 0

def plot_iperf(server, bitrates, avg_bandwidth):
    """Plot iperf bitrates over time."""
    plt.figure(figsize=(8, 5))
    plt.plot(range(len(bitrates)), bitrates, marker='o', linestyle='-', color='r')
    plt.title(f'iPerf Bandwidth for {server} (Avg: {avg_bandwidth:.2f} Mbps)')
    plt.xlabel('Interval')
    plt.ylabel('Bitrate (Mbps)')
    plt.grid(True)
    plt.savefig(f'e:\\delete\\delete_new\\iperf_{server.replace(".", "_")}.png')
    plt.show()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python iperf_graph.py <server>")
        sys.exit(1)
    server = sys.argv[1]
    bitrates, avg_bandwidth = run_iperf(server)
    if bitrates:
        plot_iperf(server, bitrates, avg_bandwidth)
    else:
        print("No bitrates to plot.")
