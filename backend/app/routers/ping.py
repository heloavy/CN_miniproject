from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.orm import Session
import asyncio
import json
import re
from collections import deque
from datetime import datetime

from ..database import get_db, SessionLocal
from ..models import PingRequest, PingResponse, PingResult
from ..services.network_tools import NetworkTools

router = APIRouter()

@router.post("/ping", response_model=PingResponse)
async def ping_endpoint(request: PingRequest, db: Session = Depends(get_db)):
    """Execute ping command and return parsed results."""
    tools = NetworkTools()
    try:
        raw_output = await tools.run_ping(request.host, request.interval)

        if "Error:" in raw_output:
            raise HTTPException(status_code=400, detail=raw_output)

        # For now, return a sample response
        return PingResponse(
            ts=datetime.utcnow(),
            rtt_ms=25.5,
            loss_pct_window=0.0,
            jitter_ms_window=2.1,
            sample_index=1
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.websocket("/ws/ping")
async def ping_websocket(websocket: WebSocket):
    """WebSocket for real-time ping data with windowed jitter and loss."""
    await websocket.accept()
    session = None
    try:
        # Receive initial request: { host, interval }
        data = await websocket.receive_text()
        request = json.loads(data)

        host = request.get("host")
        interval = float(request.get("interval", 1))
        window_size = int(request.get("window_size", 50))

        if not host:
            await websocket.send_text(json.dumps({"error": "Host is required"}))
            return

        # Prepare window trackers
        rtt_window: deque[float] = deque(maxlen=window_size)
        success_window: deque[bool] = deque(maxlen=window_size)
        sample_index = 0

        # DB session for persisting successful samples
        session = SessionLocal()

        while True:
            sample_index += 1

            # Run a single ping attempt so we can control the interval
            timeout_ms = max(1000, int(interval * 1000) + 500)
            process = await asyncio.create_subprocess_exec(
                "ping", "-n", "1", "-w", str(timeout_ms), host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                text=True,
            )

            stdout, stderr = await process.communicate()

            # Detect success / timeout and parse RTT
            rtt_ms = None
            success = False
            if process.returncode == 0 and stdout:
                # Windows ping line contains time=XXms or time<1ms
                match = re.search(r"time[<=](\d+)ms", stdout)
                if match:
                    rtt_ms = float(match.group(1))
                    success = True
                elif "time<1ms" in stdout:
                    rtt_ms = 1.0
                    success = True
            else:
                # If error or timeout
                if "Request timed out" in stdout or "timed out" in stderr:
                    success = False

            # Update windows
            success_window.append(success)
            if success and rtt_ms is not None:
                rtt_window.append(rtt_ms)

            # Compute windowed loss percentage
            if len(success_window) > 0:
                losses = sum(1 for s in success_window if not s)
                loss_pct_window = (losses / len(success_window)) * 100.0
            else:
                loss_pct_window = 0.0

            # Compute windowed jitter as mean absolute successive difference
            if len(rtt_window) >= 2:
                diffs = [abs(rtt_window[i] - rtt_window[i - 1]) for i in range(1, len(rtt_window))]
                jitter_ms_window = sum(diffs) / len(diffs)
            else:
                jitter_ms_window = 0.0

            # Build frame per contract; rtt_ms may be None on loss
            frame = {
                "ts": datetime.utcnow().isoformat(),
                "rtt_ms": rtt_ms,
                "loss_pct_window": loss_pct_window,
                "jitter_ms_window": jitter_ms_window,
                "sample_index": sample_index,
            }

            await websocket.send_text(json.dumps(frame))

            # Persist successful samples
            if success and rtt_ms is not None:
                db_row = PingResult(
                    target=host,
                    rtt_ms=rtt_ms,
                    loss_pct_window=loss_pct_window,
                    jitter_ms_window=jitter_ms_window,
                    sample_index=sample_index,
                )
                session.add(db_row)
                session.commit()

            # Respect client-specified interval
            await asyncio.sleep(interval)

    except WebSocketDisconnect:
        # Client closed connection; end gracefully
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        if session:
            session.close()
