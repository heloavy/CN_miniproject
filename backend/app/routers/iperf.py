from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import IperfRequest, IperfResponse, IperfResult
from ..services.network_tools import NetworkTools, parse_iperf_output

router = APIRouter()

@router.post("/iperf", response_model=IperfResponse)
async def iperf_endpoint(request: IperfRequest, db: Session = Depends(get_db)):
    """Execute iperf3 command and return parsed results."""
    tools = NetworkTools()
    try:
        raw_output = await tools.run_iperf(request.server, request.duration, request.protocol)

        if "Error:" in raw_output:
            raise HTTPException(status_code=400, detail=raw_output)

        # Parse the output
        parsed_metrics = parse_iperf_output(raw_output)

        # Save to database
        db_result = IperfResult(
            server=request.server,
            protocol=request.protocol,
            duration_s=request.duration,
            bandwidth_mbps=parsed_metrics["bandwidth_mbps"],
            jitter_ms=parsed_metrics["jitter_ms"],
            loss_pct=parsed_metrics["packet_loss"]
        )
        db.add(db_result)
        db.commit()

        # Return response
        return IperfResponse(
            ts=db_result.timestamp,
            server=request.server,
            protocol=request.protocol,
            duration_s=request.duration,
            bandwidth_mbps=parsed_metrics["bandwidth_mbps"],
            jitter_ms=parsed_metrics["jitter_ms"],
            loss_pct=parsed_metrics["packet_loss"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/iperf/{server}")
async def get_iperf_history(server: str, limit: int = 10, db: Session = Depends(get_db)):
    """Get iperf history for a specific server."""
    try:
        results = db.query(IperfResult)\
            .filter(IperfResult.server == server)\
            .order_by(IperfResult.timestamp.desc())\
            .limit(limit)\
            .all()

        return {
            "server": server,
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving iperf history: {str(e)}")
