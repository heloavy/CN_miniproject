from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import TracerouteRequest, TracerouteResponse, TracerouteResult
from ..services.network_tools import NetworkTools, parse_traceroute_output

router = APIRouter()

@router.post("/traceroute", response_model=TracerouteResponse)
async def traceroute_endpoint(request: TracerouteRequest, db: Session = Depends(get_db)):
    """Execute traceroute command and return parsed results."""
    tools = NetworkTools()
    try:
        raw_output = await tools.run_traceroute(request.host)

        if "Error:" in raw_output:
            raise HTTPException(status_code=400, detail=raw_output)

        # Parse the output
        hops = parse_traceroute_output(raw_output)

        # Save to database
        db_result = TracerouteResult(
            target=request.host,
            hops=hops
        )
        db.add(db_result)
        db.commit()

        # Return response
        return TracerouteResponse(
            ts=db_result.timestamp,
            host=request.host,
            hops=hops
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/traceroute/{host}")
async def get_traceroute_history(host: str, limit: int = 10, db: Session = Depends(get_db)):
    """Get traceroute history for a specific host."""
    try:
        results = db.query(TracerouteResult)\
            .filter(TracerouteResult.target == host)\
            .order_by(TracerouteResult.timestamp.desc())\
            .limit(limit)\
            .all()

        return {
            "host": host,
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving traceroute history: {str(e)}")
