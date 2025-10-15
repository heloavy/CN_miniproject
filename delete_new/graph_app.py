import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import subprocess
import platform
import re
import json
import sys

def run_ping(host, count=4):
    """Run ping and return RTT values."""
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
    except:
        return []

def run_traceroute(host):
    """Run traceroute and return hops."""
    if platform.system() == "Windows":
        cmd = ["tracert", host]
    else:
        cmd = ["traceroute", host]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.split('\n')
        hops = []
        for line in lines[4:]:
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
    except:
        return []

def run_iperf(server, duration=10):
    """Run iperf3 and return bitrates."""
    cmd = ["iperf3", "-c", server, "-t", str(duration), "-J"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        intervals = data.get("intervals", [])
        bitrates = []
        for interval in intervals:
            for stream in interval.get("streams", []):
                bitrate = stream.get("bits_per_second", 0) / (1000 * 1000)
                bitrates.append(bitrate)
        return bitrates
    except:
        return []

class GraphApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Network Test Graphs")
        self.ips = ["8.8.8.8", "1.1.1.1"]
        self.create_widgets()
        self.plot_graphs()

    def create_widgets(self):
        # IP input
        self.ip_frame = ttk.Frame(self.root)
        self.ip_frame.pack(pady=10)
        ttk.Label(self.ip_frame, text="IPs (comma-separated):").pack(side=tk.LEFT)
        self.ip_entry = ttk.Entry(self.ip_frame, width=50)
        self.ip_entry.insert(0, ",".join(self.ips))
        self.ip_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(self.ip_frame, text="Update & Plot", command=self.update_ips).pack(side=tk.LEFT)

        # Canvas for graphs
        self.fig, self.axes = plt.subplots(3, len(self.ips), figsize=(15, 10))
        if len(self.ips) == 1:
            self.axes = self.axes.reshape(3, 1)
        self.canvas = FigureCanvasTkAgg(self.fig, self.root)
        self.canvas.get_tk_widget().pack()

    def update_ips(self):
        ips_str = self.ip_entry.get()
        self.ips = [ip.strip() for ip in ips_str.split(",") if ip.strip()]
        self.plot_graphs()

    def plot_graphs(self):
        self.fig.clear()
        num_ips = len(self.ips)
        if num_ips == 1:
            axes = self.fig.subplots(3, 1, sharex=False)
            axes = axes.reshape(-1)  # Make it 1D for easy indexing
        else:
            axes = self.fig.subplots(3, num_ips, sharex=False).flatten()

        for i, ip in enumerate(self.ips):
            # Ping
            rtt_values = run_ping(ip)
            ax = axes[i * 3]
            ax.clear()
            if rtt_values:
                ax.plot(range(1, len(rtt_values) + 1), rtt_values, marker='o')
            else:
                ax.text(0.5, 0.5, 'No Ping Data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title(f'Ping RTT for {ip}')
            ax.set_xlabel('Ping Number')
            ax.set_ylabel('RTT (ms)')

            # Traceroute
            hops = run_traceroute(ip)
            ax = axes[i * 3 + 1]
            ax.clear()
            if hops:
                hop_nums = [h[0] for h in hops]
                rtts = [h[2] for h in hops if h[2] is not None]
                if rtts:
                    ax.bar(hop_nums, rtts)
                else:
                    ax.text(0.5, 0.5, 'No RTT Data', ha='center', va='center', transform=ax.transAxes)
            else:
                ax.text(0.5, 0.5, 'No Hops', ha='center', va='center', transform=ax.transAxes)
            ax.set_title(f'Traceroute RTT for {ip}')
            ax.set_xlabel('Hop Number')
            ax.set_ylabel('RTT (ms)')

            # iPerf
            bitrates = run_iperf(ip)
            ax = axes[i * 3 + 2]
            ax.clear()
            if bitrates:
                ax.plot(range(len(bitrates)), bitrates, marker='o')
            else:
                ax.text(0.5, 0.5, 'No iPerf Data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title(f'iPerf Bandwidth for {ip}')
            ax.set_xlabel('Interval')
            ax.set_ylabel('Bitrate (Mbps)')

        self.fig.tight_layout()
        self.canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    app = GraphApp(root)
    root.mainloop()
