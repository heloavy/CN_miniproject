from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PingResult, TracerouteResult, IperfResult

router = APIRouter()

@router.get("/history")
async def history_endpoint(
    tool: str = Query(..., description="Tool type: ping, traceroute, or iperf"),
    target: str = Query(..., description="Target host or server"),
    limit: int = Query(50, description="Number of results to return"),
    db: Session = Depends(get_db)
):
    """Get history for any network tool."""
    try:
        if tool.lower() == "ping":
            results = db.query(PingResult)\
                .filter(PingResult.target == target)\
                .order_by(PingResult.timestamp.desc())\
                .limit(limit)\
                .all()
            return {
                "tool": tool,
                "target": target,
                "results": [
                    {
                        "id": result.id,
                        "timestamp": result.timestamp,
                        "target": result.target,
                        "rtt_ms": result.rtt_ms,
                        "loss_pct_window": result.loss_pct_window,
                        "jitter_ms_window": result.jitter_ms_window,
                        "sample_index": result.sample_index
                    }
                    for result in results
                ]
            }
        elif tool.lower() == "traceroute":
            results = db.query(TracerouteResult)\
                .filter(TracerouteResult.target == target)\
                .order_by(TracerouteResult.timestamp.desc())\
                .limit(limit)\
                .all()
            return {
                "tool": tool,
                "target": target,
                "results": [
                    {
                        "id": result.id,
                        "timestamp": result.timestamp,
                        "target": result.target,
                        "hops": result.hops
                    }
                    for result in results
                ]
            }
        elif tool.lower() == "iperf":
            results = db.query(IperfResult)\
                .filter(IperfResult.server == target)\
                .order_by(IperfResult.timestamp.desc())\
                .limit(limit)\
                .all()
            return {
                "tool": tool,
                "target": target,
                "results": [
                    {
                        "id": result.id,
                        "timestamp": result.timestamp,
                        "server": result.server,
                        "protocol": result.protocol,
                        "duration_s": result.duration_s,
                        "bandwidth_mbps": result.bandwidth_mbps,
                        "jitter_ms": result.jitter_ms,
                        "loss_pct": result.loss_pct
                    }
                    for result in results
                ]
            }
        else:
            raise HTTPException(status_code=400, detail="Invalid tool type. Use 'ping', 'traceroute', or 'iperf'.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving history: {str(e)}")
