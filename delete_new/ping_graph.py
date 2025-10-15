import subprocess
import platform
import re
import matplotlib.pyplot as plt
import sys

def run_ping(host, count=4):
    """Run ping command and return RTT values."""
    if platform.system() == "Windows":
        cmd = ["ping", "-n", str(count), host]
    else:
        cmd = ["ping", "-c", str(count), host]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.split('\n')
        rtt_values = []
        for line in lines:
            if 'time=' in line or 'time<' in line:
                if 'time=' in line:
                    match = re.search(r'time[<=](\d+)ms', line)
                    if match:
                        rtt_values.append(int(match.group(1)))
                elif 'time<1ms' in line:
                    rtt_values.append(1)
        return rtt_values
    except subprocess.CalledProcessError as e:
        print(f"Ping failed: {e}")
        return []

def plot_ping(host, rtt_values):
    """Plot ping RTT values."""
    plt.figure(figsize=(8, 5))
    plt.plot(range(1, len(rtt_values) + 1), rtt_values, marker='o', linestyle='-', color='b')
    plt.title(f'Ping RTT for {host}')
    plt.xlabel('Ping Number')
    plt.ylabel('RTT (ms)')
    plt.grid(True)
    plt.savefig(f'e:\\delete\\delete_new\\ping_{host.replace(".", "_")}.png')
    plt.show()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python ping_graph.py <host>")
        sys.exit(1)
    host = sys.argv[1]
    rtt_values = run_ping(host)
    if rtt_values:
        plot_ping(host, rtt_values)
    else:
        print("No RTT values to plot.")
