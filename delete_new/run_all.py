import subprocess
import sys

# Define nodes (IPs or hostnames)
nodes = ["8.8.8.8", "1.1.1.1", "127.0.0.1"]  # Example nodes

def run_for_node(node):
    """Run all tools for a node."""
    print(f"Running tests for {node}")
    
    # Ping
    print("Running ping...")
    subprocess.run([sys.executable, "ping_graph.py", node])
    
    # Traceroute
    print("Running traceroute...")
    subprocess.run([sys.executable, "traceroute_graph.py", node])
    
    # iPerf (assuming iperf server on node, but for demo, skip if local)
    if node != "127.0.0.1":
        print("Running iperf...")
        subprocess.run([sys.executable, "iperf_graph.py", node])

if __name__ == "__main__":
    for node in nodes:
        run_for_node(node)
    print("All tests completed. Check e:\\delete\\delete_new for graphs.")
