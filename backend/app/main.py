
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
from pydantic import BaseModel, Field

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

async def run_cmd(*args, timeout: float = None):
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
        if timeout:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        else:
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
    # Log connection
    try:
        client = websocket.client
    except Exception:
        client = None
    print(f"[ws_ping] Connection accepted from: {client}")
    # Send initial handshake ack to client
    try:
        await websocket.send_text(json.dumps({"type": "info", "message": "ws connected"}))
    except Exception:
        pass

    try:
        # Wait for start message from client
        msg = json.loads(await websocket.receive_text())
        host = msg.get("host")
        interval = int(float(msg.get("interval", 1)) * 1000)  # Convert seconds to ms
        # window_size is ignored in backend

        if not host:
            await websocket.send_text(json.dumps({"type": "error", "error": "Host is required"}))
            return

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


@app.websocket("/ws/traceroute")
async def ws_traceroute(websocket: WebSocket):
    """WebSocket to stream traceroute output line-by-line."""
    await websocket.accept()
    try:
        client = websocket.client
    except Exception:
        client = None
    print(f"[ws_traceroute] Connection accepted from: {client}")
    try:
        await websocket.send_text(json.dumps({"type": "info", "message": "ws connected"}))
    except Exception:
        pass

    try:
        msg = json.loads(await websocket.receive_text())
        host = msg.get("host")
        if not host:
            await websocket.send_text(json.dumps({"type": "error", "error": "Host is required"}))
            return

        await _stream_traceroute(websocket, host)

    except WebSocketDisconnect:
        return
    except json.JSONDecodeError:
        await websocket.send_text(json.dumps({"type": "error", "error": "Invalid JSON message"}))
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))
        except:
            pass


async def _stream_traceroute(websocket: WebSocket, host: str):
    """Run tracert and stream parsed hops as they appear."""
    hops = []
    try:
        # Start tracert process and read stdout line by line
        process = await asyncio.create_subprocess_exec(
            "tracert", host,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        # Read lines as they arrive
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            text = line.decode('utf-8', errors='ignore').strip()
            # Send raw line for debugging
            try:
                await websocket.send_text(json.dumps({"type": "line", "text": text}))
            except Exception:
                pass

            # Parse hop lines (start with digit)
            if text and text[0].isdigit():
                try:
                    # hop number is first token
                    hop_num = int(text.split()[0])
                except Exception:
                    continue

                # Extract RTTs using regex to match '<1 ms', '1 ms', '123 ms', '<1ms', etc.
                rtt_matches = re.findall(r"<?\d+(?:\.\d+)?\s*ms", text)
                rtts = []
                for match in rtt_matches:
                    cleaned = match.replace('ms', '').strip()
                    cleaned = cleaned.replace('<', '')
                    try:
                        rtts.append(float(cleaned))
                    except Exception:
                        pass

                # Extract last IP-like token if present
                ip_match = re.findall(r"(\d{1,3}(?:\.\d{1,3}){3})", text)
                ip = ip_match[-1] if ip_match else '*'

                rtt = min(rtts) if rtts else None
                hop = {"hop": hop_num, "ip": ip, "rtt_ms": rtt}
                hops.append(hop)

                # send parsed hop
                try:
                    await websocket.send_text(json.dumps({"type": "hop", "hop": hop}))
                except Exception:
                    return

        # Wait for process to finish
        await process.wait()

        # Send done frame with aggregated hops
        try:
            await websocket.send_text(json.dumps({"type": "done", "hops": hops, "ts": now_iso()}))
        except Exception:
            pass

        # Save to CSV
        traceroute_data = {"target": host, "hops": hops, "timestamp": now_iso()}
        save_to_csv("traceroute", traceroute_data)

    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))
        except Exception:
            pass

async def _stream_ping(websocket: WebSocket, host: str, interval_ms: int):
    """Stream real ping data."""
    window: List[float] = []
    idx = 0

    try:
        error_count = 0
        while True:
            out = await run_cmd("ping", "-n", "1", "-w", "1000", host)
            rtt = parse_ping_rtt_ms(out)

            if rtt is not None:
                window.append(rtt)
                if len(window) > 20:
                    window.pop(0)
                summary = summarize_window(window)
                try:
                    await websocket.send_text(json.dumps({
                        "type": "sample",
                        "ts": now_iso(),
                        "sample_index": idx,
                        "rtt_ms": rtt,
                        "jitter_ms_window": summary["jitter_ms"],
                        "loss_pct_window": summary["loss_pct"]
                    }))
                except Exception:
                    # If the client disconnected or the socket is closing, stop streaming
                    return
                ping_data = {
                    "target": host,
                    "rtt_ms": rtt,
                    "loss_pct_window": summary["loss_pct"],
                    "jitter_ms_window": summary["jitter_ms"],
                    "sample_index": idx,
                }
                save_to_csv("ping", ping_data)
                error_count = 0
            else:
                # Emit a null sample so frontend can show packet loss (latency = null)
                error_count += 1
                summary = summarize_window(window)
                # Send a sample with rtt_ms = null to represent a lost packet
                try:
                    await websocket.send_text(json.dumps({
                        "type": "sample",
                        "ts": now_iso(),
                        "sample_index": idx,
                        "rtt_ms": None,
                        "jitter_ms_window": summary["jitter_ms"],
                        "loss_pct_window": 100.0 if not window else summary["loss_pct"]
                    }))
                except Exception:
                    return

                # Also send a human-readable error frame for diagnostics
                try:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "error": f"Ping failed for {host}. Output: {out}",
                        "sample_index": idx
                    }))
                except Exception:
                    return

                # Throttle sustained failure bursts to avoid tight loops
                # After many consecutive failures pause briefly but *do not* close the stream.
                if error_count >= 30:
                    await asyncio.sleep(5)
                    # reset count after a pause so we keep streaming diagnostic null samples
                    error_count = 0

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
        out = await run_cmd("tracert", request.host, timeout=15.0)

        if "Unable to resolve target system name" in out:
            raise HTTPException(status_code=400, detail="Unable to resolve hostname")

        hops = parse_tracert(out)

        # If no hops were parsed, return raw output and empty hops instead of
        # failing with a 500. This preserves diagnostics for the client.
        if not hops:
            traceroute_data = {
                "target": request.host,
                "hops": [],
                "raw": out
            }
            save_to_csv("traceroute", traceroute_data)
            return {
                "ts": now_iso(),
                "host": request.host,
                "hops": [],
                "raw": out,
                "message": "No hops parsed from tracert output; raw output included"
            }

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
            # Convert iperf3 interval format to frontend format. iperf3 may put
            # interval sums either in interval_data['sum'] or inside each stream
            # at interval_data['streams'][i]['sum']. We'll handle both.
            result["intervals"] = []
            for idx, interval_data in enumerate(intervals):
                # Prefer top-level sum
                sum_interval = interval_data.get("sum") or {}

                # If not present, try streams -> sum
                if not sum_interval and interval_data.get("streams"):
                    stream = interval_data["streams"][0]
                    sum_interval = stream.get("sum", {})

                # Start/end may be under sum
                start = sum_interval.get("start")
                end = sum_interval.get("end")

                # bits_per_second may be under sum
                bits_per_second = sum_interval.get("bits_per_second") or sum_interval.get("bits_per_second", 0)
                bytes_transferred = sum_interval.get("bytes", 0)

                # Fallbacks: some iperf outputs include bytes/bits under different keys
                if not bits_per_second:
                    bits_per_second = sum_interval.get("bits_per_second", 0)

                # Build interval label
                if start is not None and end is not None:
                    interval_label = f"{float(start):.1f}-{float(end):.1f}"
                elif isinstance(interval_data.get("interval"), (list, tuple)):
                    # sometimes interval is [start, end]
                    s, e = interval_data.get("interval")
                    interval_label = f"{float(s):.1f}-{float(e):.1f}"
                else:
                    # fallback to index-based label
                    interval_label = f"{idx}.0-{idx+1}.0"

                result["intervals"].append({
                    "interval": interval_label,
                    "transfer": round((bytes_transferred or 0) / (1024 * 1024), 2),  # Convert to MBytes
                    "bitrate": round((bits_per_second or 0) / 1_000_000, 2)  # Convert to Mbps
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
        raw = await run_cmd(*args, timeout=request.duration + 10)

        if "connect failed" in raw.lower():
            raise HTTPException(status_code=400, detail="Failed to connect to iperf3 server")
        if not raw or raw.strip() == "":
            raise HTTPException(status_code=500, detail=f"iperf3 returned no output. Raw: {raw}")

        # If iperf returned non-JSON, log raw output for debugging
        try:
            json.loads(raw)
        except Exception:
            print('[iperf] Raw output (non-JSON):')
            print(raw)
            # continue and let parse_iperf3_json raise a helpful HTTPException

        try:
            result = parse_iperf3_json(raw)
        except HTTPException:
            # Re-raise to preserve HTTPException details
            raise
        except Exception as e:
            # Include raw iperf output for debugging
            raise HTTPException(status_code=500, detail=f"iperf3 parse/processing error: {e}. Raw: {raw}")
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

# ---------- Enhanced Node Actions and Measurement Integration ----------

class NodeActionReq(BaseModel):
    node_id: str = Field(..., description="ID of the node to perform action on")
    action: str = Field(..., description="Action to perform: ping, traceroute, or iperf")

class BulkPingReq(BaseModel):
    node_ids: List[str] = Field(..., description="List of node IDs to ping")
    rate_limit_ms: int = Field(100, description="Rate limit between pings in milliseconds", gt=0)

class BulkPingResult(BaseModel):
    node_id: str = Field(..., description="ID of the node that was pinged")
    node_label: str = Field(..., description="Label of the node")
    target_ip: str = Field(..., description="IP address that was pinged")
    latency_ms: Optional[float] = Field(None, description="Measured latency")
    success: bool = Field(..., description="Whether the ping was successful")
    timestamp: float = Field(..., description="Unix timestamp of the measurement")
    error: Optional[str] = Field(None, description="Error message if ping failed")

@app.post("/api/node-action")
async def node_action_endpoint(request: NodeActionReq):
    """Perform a measurement action on a specific node."""
    try:
        # This would typically look up the node in a database to get its IP
        # For now, we'll assume node_id maps to IP address
        target_ip = request.node_id  # Simplified mapping

        if request.action.lower() == "ping":
            out = await run_cmd("ping", "-n", "1", "-w", "1000", target_ip)
            rtt = parse_ping_rtt_ms(out)
            if rtt is None:
                raise HTTPException(status_code=408, detail="Ping timed out or host unreachable")

            result = {
                "ts": now_iso(),
                "node_id": request.node_id,
                "action": "ping",
                "target": target_ip,
                "rtt_ms": rtt,
                "success": True
            }

        elif request.action.lower() == "traceroute":
            out = await run_cmd("tracert", target_ip)
            if "Unable to resolve target system name" in out:
                raise HTTPException(status_code=400, detail="Unable to resolve hostname")

            hops = parse_tracert(out)
            if not hops:
                raise HTTPException(status_code=500, detail="Failed to parse tracert output")

            result = {
                "ts": now_iso(),
                "node_id": request.node_id,
                "action": "traceroute",
                "target": target_ip,
                "hops": hops,
                "success": True
            }

        elif request.action.lower() == "iperf":
            # For iperf, we need to check if the node is configured as an iperf server
            # This would require additional node metadata in a real implementation
            args = ["iperf3", "-c", target_ip, "-t", "10", "-J"]
            raw = await run_cmd(*args)

            if "connect failed" in raw.lower():
                raise HTTPException(status_code=400, detail="Failed to connect to iperf3 server")

            iperf_result = parse_iperf3_json(raw)
            result = {
                "ts": now_iso(),
                "node_id": request.node_id,
                "action": "iperf",
                "target": target_ip,
                "result": iperf_result,
                "success": True
            }

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")

        # Save to appropriate CSV file
        save_to_csv(request.action.lower(), result)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error performing {request.action}: {str(e)}")

@app.post("/api/bulk-ping")
async def bulk_ping_endpoint(request: BulkPingReq):
    """Perform ping operations on multiple nodes with rate limiting."""
    try:
        results = []
        rate_limit_seconds = request.rate_limit_ms / 1000.0

        for node_id in request.node_ids:
            # Simplified node ID to IP mapping
            target_ip = node_id

            try:
                out = await run_cmd("ping", "-n", "1", "-w", "1000", target_ip)
                rtt = parse_ping_rtt_ms(out)

                result = BulkPingResult(
                    node_id=node_id,
                    node_label=f"Node {node_id}",  # Would be looked up from database
                    target_ip=target_ip,
                    latency_ms=rtt,
                    success=rtt is not None,
                    timestamp=datetime.now().timestamp(),
                    error=None if rtt is not None else "Ping failed or timed out"
                )

                # Save individual ping result
                ping_data = {
                    "target": target_ip,
                    "rtt_ms": rtt,
                    "node_id": node_id
                }
                save_to_csv("ping", ping_data)

            except Exception as e:
                result = BulkPingResult(
                    node_id=node_id,
                    node_label=f"Node {node_id}",
                    target_ip=target_ip,
                    latency_ms=None,
                    success=False,
                    timestamp=datetime.now().timestamp(),
                    error=str(e)
                )

            results.append(result)

            # Rate limiting between requests
            if rate_limit_seconds > 0:
                await asyncio.sleep(rate_limit_seconds)

        return {"results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in bulk ping operation: {str(e)}")

@app.get("/api/traceroute-overlay/{node_id}")
async def traceroute_overlay_endpoint(node_id: str):
    """Get traceroute overlay data for mapping hops to network topology."""
    try:
        # Get recent traceroute data for this node
        traceroute_history = load_from_csv("traceroute", node_id, limit=5)

        if not traceroute_history:
            raise HTTPException(status_code=404, detail="No traceroute data found for this node")

        # Get the most recent traceroute
        latest_traceroute = traceroute_history[0]

        # This would typically involve:
        # 1. Looking up node positions and connections from a database
        # 2. Matching traceroute hops to known nodes/edges
        # 3. Calculating positions for unmatched hops

        # For now, return the traceroute data with basic overlay information
        overlay_data = {
            "node_id": node_id,
            "traceroute_path": latest_traceroute.get("hops", []),
            "matched_edges": [],  # Would contain matched edge IDs and RTT deltas
            "unmatched_hops": [], # Would contain hops that couldn't be matched
            "timestamp": latest_traceroute.get("timestamp")
        }

        return overlay_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating traceroute overlay: {str(e)}")

@app.get("/api/measurements/{node_id}")
async def node_measurements_endpoint(
    node_id: str,
    tool: str = Query(..., description="Tool type: ping, traceroute, or iperf"),
    limit: int = Query(50, description="Number of results to return")
):
    """Get measurement history for a specific node."""
    try:
        results = load_from_csv(tool.lower(), node_id, limit)

        # Enhance results with node-specific metadata
        enhanced_results = []
        for result in results:
            enhanced_result = {
                **result,
                "node_id": node_id,
                "tool": tool.lower()
            }
            enhanced_results.append(enhanced_result)

        return {
            "node_id": node_id,
            "tool": tool,
            "results": enhanced_results,
            "total_count": len(enhanced_results)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving measurements: {str(e)}")

@app.get("/api/measurements/summary/{node_id}")
async def node_measurements_summary_endpoint(node_id: str):
    """Get measurement summary for a node including SLA breach information."""
    try:
        # Get recent measurements across all tools
        ping_results = load_from_csv("ping", node_id, limit=100)
        traceroute_results = load_from_csv("traceroute", node_id, limit=10)
        iperf_results = load_from_csv("iperf", node_id, limit=10)

        # Calculate summary statistics
        summary = {
            "node_id": node_id,
            "last_updated": now_iso(),
            "measurements": {
                "ping": {
                    "count": len(ping_results),
                    "latest": ping_results[0] if ping_results else None,
                    "avg_latency_ms": None,
                    "success_rate": None
                },
                "traceroute": {
                    "count": len(traceroute_results),
                    "latest": traceroute_results[0] if traceroute_results else None,
                    "avg_hop_count": None
                },
                "iperf": {
                    "count": len(iperf_results),
                    "latest": iperf_results[0] if iperf_results else None,
                    "avg_bandwidth_mbps": None
                }
            }
        }

        # Calculate averages if we have data
        if ping_results:
            latencies = [r.get("rtt_ms") for r in ping_results if r.get("rtt_ms") is not None]
            if latencies:
                summary["measurements"]["ping"]["avg_latency_ms"] = sum(latencies) / len(latencies)
                summary["measurements"]["ping"]["success_rate"] = len(latencies) / len(ping_results)

        if traceroute_results:
            hop_counts = [len(r.get("hops", [])) for r in traceroute_results if r.get("hops")]
            if hop_counts:
                summary["measurements"]["traceroute"]["avg_hop_count"] = sum(hop_counts) / len(hop_counts)

        if iperf_results:
            bandwidths = [r.get("bandwidth_mbps") for r in iperf_results if r.get("bandwidth_mbps") is not None]
            if bandwidths:
                summary["measurements"]["iperf"]["avg_bandwidth_mbps"] = sum(bandwidths) / len(bandwidths)

        return summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating measurement summary: {str(e)}")

@app.get("/api/health")
async def health_endpoint():
    """Enhanced health check with tool availability information."""
    try:
        health_info = {
            "status": "healthy",
            "timestamp": now_iso(),
            "tools": {}
        }

        # Check tool availability
        tools_to_check = {
            "ping": ["ping", "-n", "1", "-w", "1000", "127.0.0.1"],
            "tracert": ["tracert", "127.0.0.1"],
            "iperf3": ["iperf3", "--version"]
        }

        for tool_name, test_cmd in tools_to_check.items():
            try:
                # Use a short timeout for health checks
                process = await asyncio.create_subprocess_exec(
                    *test_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)
                health_info["tools"][tool_name] = "available"
            except asyncio.TimeoutError:
                health_info["tools"][tool_name] = "timeout"
            except FileNotFoundError:
                health_info["tools"][tool_name] = "not_found"
            except Exception as e:
                health_info["tools"][tool_name] = f"error: {str(e)}"

        return health_info

    except Exception as e:
        return {
            "status": "error",
            "timestamp": now_iso(),
            "error": str(e),
            "tools": {}
        }

@app.post("/api/measurements/reconcile-traceroute")
async def reconcile_traceroute_endpoint(request: NodeActionReq):
    """Reconcile traceroute results with network topology to update edge measurements."""
    try:
        # This would:
        # 1. Run a traceroute for the node
        # 2. Match hops to existing nodes/edges in the topology
        # 3. Update edge measurement data with RTT deltas
        # 4. Return reconciliation results

        # For now, return a placeholder response
        reconciliation_result = {
            "node_id": request.node_id,
            "timestamp": now_iso(),
            "action_performed": request.action,
            "matched_edges": [],
            "unmatched_hops": [],
            "updated_measurements": 0
        }

        return reconciliation_result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reconciling traceroute: {str(e)}")

# ---------- Periodic Monitoring ----------

monitoring_tasks = {}

@app.post("/api/monitoring/start")
async def start_monitoring_endpoint(request: NodeActionReq):
    """Start periodic monitoring for a node."""
    try:
        # This would start a background task for periodic monitoring
        # For now, just return success
        return {
            "node_id": request.node_id,
            "monitoring_started": True,
            "interval_minutes": 5,  # Default interval
            "timestamp": now_iso()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting monitoring: {str(e)}")

@app.post("/api/monitoring/stop")
async def stop_monitoring_endpoint(request: NodeActionReq):
    """Stop periodic monitoring for a node."""
    try:
        return {
            "node_id": request.node_id,
            "monitoring_stopped": True,
            "timestamp": now_iso()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error stopping monitoring: {str(e)}")
