import subprocess
import platform
import re
import matplotlib.pyplot as plt
import sys

def run_traceroute(host):
    """Run traceroute command and return hops with RTT."""
    if platform.system() == "Windows":
        cmd = ["tracert", host]
    else:
        cmd = ["traceroute", host]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.split('\n')
        hops = []
        for line in lines[4:]:  # Skip header
            if line.strip() and not line.startswith('Trace complete'):
                parts = line.strip().split()
                if len(parts) >= 3:
                    hop_num = int(parts[0])
                    ip = parts[1]
                    rtt_values = []
                    for part in parts[2:]:
                        if 'ms' in part:
                            match = re.search(r'(\d+)ms', part)
                            if match:
                                rtt_values.append(int(match.group(1)))
                            elif '<1ms' in part:
                                rtt_values.append(1)
                    avg_rtt = sum(rtt_values) / len(rtt_values) if rtt_values else None
                    hops.append((hop_num, ip, avg_rtt))
        return hops
    except subprocess.CalledProcessError as e:
        print(f"Traceroute failed: {e}")
        return []

def plot_traceroute(host, hops):
    """Plot traceroute RTT per hop."""
    hop_nums = [hop[0] for hop in hops]
    rtts = [hop[2] for hop in hops if hop[2] is not None]
    plt.figure(figsize=(10, 6))
    plt.bar(hop_nums, rtts, color='g')
    plt.title(f'Traceroute RTT for {host}')
    plt.xlabel('Hop Number')
    plt.ylabel('RTT (ms)')
    plt.xticks(hop_nums)
    plt.grid(True, axis='y')
    plt.savefig(f'e:\\delete\\delete_new\\traceroute_{host.replace(".", "_")}.png')
    plt.show()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python traceroute_graph.py <host>")
        sys.exit(1)
    host = sys.argv[1]
    hops = run_traceroute(host)
    if hops:
        plot_traceroute(host, hops)
    else:
        print("No hops to plot.")
