import asyncio
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional
import statistics as stdev

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import CSV storage functions
from .models import save_to_csv, load_from_csv, TraceReq, IperfReq

def now_iso(): 
    return datetime.now(timezone.utc).isoformat()

app = FastAPI(title="Network Performance Monitor API", version="1.0.0")

# CORS middleware - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def run_cmd(*args):
    """Run a command and return output."""
    try:
        # Use full path for iperf3 if it's not in PATH
        if args[0] == "iperf3" and len(args) > 0:
            iperf3_path = r"E:\delete\iperf3.19.1_64\iperf3.19.1_64\iperf3.exe"
            if os.path.exists(iperf3_path):
                args = (iperf3_path,) + args[1:]

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        stdout, stderr = await process.communicate()
        return stdout.decode('utf-8', errors='ignore')
    except Exception as e:
        return str(e)

# ---------- Ping (Windows) ----------
PING_RTT = re.compile(r"time[=<]\s*(\d+)\s*ms", re.IGNORECASE)

def parse_ping_rtt_ms(output: str) -> Optional[float]:
    """Parse RTT from ping output, return None if timeout."""
    m = PING_RTT.search(output)
    return float(m.group(1)) if m else None

def summarize_window(samples: List[float]) -> Dict[str, float]:
    """Calculate jitter and loss from RTT samples."""
    if not samples:
        return {"jitter_ms": 0.0, "loss_pct": 100.0}
    if len(samples) < 2:
        return {"jitter_ms": 0.0, "loss_pct": 0.0}

    deltas = [abs(samples[i] - samples[i-1]) for i in range(1, len(samples))]
    jitter = stdev(deltas) if len(deltas) > 1 else (deltas[0] if deltas else 0.0)
    return {"jitter_ms": float(jitter), "loss_pct": 0.0}

# ---------- WebSocket Ping ----------
@app.websocket("/ws/ping")
async def ws_ping(websocket: WebSocket):
    """WebSocket for real-time ping data streaming."""
    await websocket.accept()

    try:
        # Wait for start message from client
        msg = json.loads(await websocket.receive_text())
        if msg.get("action") != "start":
            await websocket.send_text(json.dumps({"type": "error", "error": "Expected start action"}))
            return

        host = msg["host"]
        interval = int(msg.get("interval_ms", 1000))

        # Start streaming ping data
        await _stream_ping(websocket, host, interval)

    except WebSocketDisconnect:
        pass
    except json.JSONDecodeError:
        await websocket.send_text(json.dumps({"type": "error", "error": "Invalid JSON message"}))
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))
        except:
            pass

async def _stream_ping(websocket: WebSocket, host: str, interval_ms: int):
    """Stream real ping data."""
    window: List[float] = []
    idx = 0

    try:
        while True:
            # Run Windows ping command correctly
            out = await run_cmd("ping", "-n", "1", "-w", "1000", host)  # -w 1000 for 1 second timeout
            rtt = parse_ping_rtt_ms(out)

            # Update window for jitter calculation
            if rtt is not None:
                window.append(rtt)
                if len(window) > 20:
                    window.pop(0)

            summary = summarize_window(window)

            # Send data to client
            await websocket.send_text(json.dumps({
                "type": "sample",
                "ts": now_iso(),
                "sample_index": idx,
                "rtt_ms": rtt,
                "jitter_ms_window": summary["jitter_ms"],
                "loss_pct_window": summary["loss_pct"]
            }))

            # Store successful ping results in CSV
            if rtt is not None:
                ping_data = {
                    "target": host,
                    "rtt_ms": rtt,
                    "loss_pct_window": summary["loss_pct"],
                    "jitter_ms_window": summary["jitter_ms"],
                    "sample_index": idx,
                }
                save_to_csv("ping", ping_data)

            idx += 1
            await asyncio.sleep(max(0.1, interval_ms / 1000.0))

    except asyncio.CancelledError:
        return
    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))
        except:
            pass

# ---------- Traceroute (Windows tracert) ----------
class TraceReq(BaseModel):
    host: str

def parse_tracert(output: str):
    """Parse Windows tracert output."""
    hops = []
    lines = output.splitlines()

    for line in lines:
        line = line.strip()
        if not line or not line[0].isdigit():
            continue

        parts = line.split()

        # Handle different Windows tracert output formats
        if len(parts) < 2:
            continue

        try:
            hop_num = int(parts[0])
        except (ValueError, IndexError):
            continue

        # Extract RTT values (handle multiple RTTs per hop)
        rtts = []
        for part in parts[1:]:
            part = part.strip()
            if part.endswith("ms") and part[:-2].replace(".", "").replace("-", "").isdigit():
                try:
                    # Handle cases like "<1 ms" or "1 ms"
                    rtt_str = part[:-2].strip('<>')
                    if rtt_str.replace(".", "").isdigit():
                        rtts.append(float(rtt_str))
                except ValueError:
                    pass

        # Get IP/hostname (usually the last part)
        ip = "*"
        for part in reversed(parts[1:]):
            if not part.endswith("ms") and part not in ["*", "Request", "timed", "out"]:
                ip = part
                break

        hops.append({
            "hop": hop_num,
            "ip": ip,
            "rtt_ms": min(rtts) if rtts else None
        })

    return hops

@app.post("/api/traceroute")
async def traceroute_endpoint(request: TraceReq):
    """Execute Windows tracert command and return parsed results."""
    try:
        out = await run_cmd("tracert", request.host)

        if "Unable to resolve target system name" in out:
            raise HTTPException(status_code=400, detail="Unable to resolve hostname")

        hops = parse_tracert(out)

        if not hops:
            raise HTTPException(status_code=500, detail="Failed to parse tracert output")

        # Save to CSV
        traceroute_data = {
            "target": request.host,
            "hops": hops
        }
        save_to_csv("traceroute", traceroute_data)

        return {
            "ts": now_iso(),
            "host": request.host,
            "hops": hops
        }

    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="tracert command not found in PATH")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running tracert: {str(e)}")

# ---------- iPerf3 ----------
class IperfReq(BaseModel):
    server: str
    duration: int = 10
    protocol: str = "tcp"

def parse_iperf3_json(raw: str) -> Dict:
    """Parse iperf3 JSON output."""
    try:
        data = json.loads(raw)
        result = {}

        # Extract from end.sum or end.sum_received
        end_data = data.get("end", {})
        sum_data = end_data.get("sum") or end_data.get("sum_received") or {}

        # Bandwidth in Mbps
        bps = sum_data.get("bits_per_second", 0)
        result["bandwidth_mbps"] = round(bps / 1_000_000.0, 3)

        # UDP-specific fields
        if "jitter_ms" in sum_data:
            result["jitter_ms"] = float(sum_data.get("jitter_ms", 0.0))

            # Calculate packet loss percentage
            packets = sum_data.get("packets", 0)
            lost = sum_data.get("lost_packets", 0)
            result["loss_pct"] = round(100.0 * (lost / packets), 3) if packets else 0.0

        # Include real interval data from iperf3 output
        intervals = data.get("intervals", [])
        if intervals:
            # Convert iperf3 interval format to frontend format
            result["intervals"] = []
            for interval_data in intervals:
                if interval_data.get("streams"):
                    stream = interval_data["streams"][0]
                    sum_interval = stream.get("sum", {})

                    # Extract transfer and bitrate from iperf3 interval data
                    bytes_transferred = sum_interval.get("bytes", 0)
                    bits_per_second = sum_interval.get("bits_per_second", 0)

                    result["intervals"].append({
                        "interval": interval_data.get("sum", {}).get("start", 0),
                        "transfer": round(bytes_transferred / (1024 * 1024), 2),  # Convert to MBytes
                        "bitrate": round(bits_per_second / 1_000_000, 2)  # Convert to Mbps
                    })

        return result

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"iperf3 JSON parse error: {e}")

@app.post("/api/iperf")
async def iperf_endpoint(request: IperfReq):
    """Execute iperf3 command and return parsed results."""
    try:
        args = ["iperf3", "-c", request.server, "-t", str(request.duration), "-J"]

        if request.protocol.lower() == "udp":
            args.insert(1, "-u")

        raw = await run_cmd(*args)

        if "connect failed" in raw.lower():
            raise HTTPException(status_code=400, detail="Failed to connect to iperf3 server")

        result = parse_iperf3_json(raw)
        result.update({
            "ts": now_iso(),
            "server": request.server,
            "protocol": request.protocol,
            "duration_s": request.duration
        })

        # Save to CSV
        save_to_csv("iperf", result)

        return result

    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="iperf3 command not found in PATH")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running iperf3: {str(e)}")

# ---------- History Endpoint ----------
@app.get("/api/history")
async def history_endpoint(
    tool: str = Query(..., description="Tool type: ping, traceroute, or iperf"),
    target: str = Query(..., description="Target host or server"),
    limit: int = Query(50, description="Number of results to return")
):
    """Get history for any network tool from CSV files."""
    try:
        # Load data from CSV files
        results = load_from_csv(tool.lower(), target, limit)

        return {
            "tool": tool,
            "target": target,
            "results": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving history: {str(e)}")

# ---------- Root endpoint ----------
@app.get("/")
async def root():
    return {"message": "Network Performance Monitor API", "os": "windows"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="10.253.21.196", port=8000)
