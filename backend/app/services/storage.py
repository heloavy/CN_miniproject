from sqlalchemy.orm import Session
from ..models import PingResult, TracerouteResult, IperfResult
from datetime import datetime
import json

def save_ping_result(db: Session, target: str, raw_output: str, parsed_metrics: dict):
    """Save ping result to database."""
    db_result = PingResult(
        target=target,
        raw_output=raw_output,
        parsed_metrics=json.dumps(parsed_metrics),
        timestamp=datetime.utcnow()
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result

def save_traceroute_result(db: Session, target: str, raw_output: str, parsed_metrics: list):
    """Save traceroute result to database."""
    db_result = TracerouteResult(
        target=target,
        raw_output=raw_output,
        parsed_metrics=json.dumps(parsed_metrics),
        timestamp=datetime.utcnow()
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result

def save_iperf_result(db: Session, target: str, raw_output: str, parsed_metrics: dict):
    """Save iperf result to database."""
    db_result = IperfResult(
        target=target,
        raw_output=raw_output,
        parsed_metrics=json.dumps(parsed_metrics),
        timestamp=datetime.utcnow()
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result

def get_ping_history(db: Session, target: str, limit: int = 10):
    """Get recent ping results for a target."""
    results = db.query(PingResult)\
        .filter(PingResult.target == target)\
        .order_by(PingResult.timestamp.desc())\
        .limit(limit)\
        .all()

    return [
        {
            "id": result.id,
            "timestamp": result.timestamp,
            "target": result.target,
            "raw_output": result.raw_output,
            "parsed_metrics": json.loads(result.parsed_metrics) if result.parsed_metrics else {}
        }
        for result in results
    ]

def get_traceroute_history(db: Session, target: str, limit: int = 10):
    """Get recent traceroute results for a target."""
    results = db.query(TracerouteResult)\
        .filter(TracerouteResult.target == target)\
        .order_by(TracerouteResult.timestamp.desc())\
        .limit(limit)\
        .all()

    return [
        {
            "id": result.id,
            "timestamp": result.timestamp,
            "target": result.target,
            "raw_output": result.raw_output,
            "parsed_metrics": json.loads(result.parsed_metrics) if result.parsed_metrics else []
        }
        for result in results
    ]

def get_iperf_history(db: Session, target: str, limit: int = 10):
    """Get recent iperf results for a target."""
    results = db.query(IperfResult)\
        .filter(IperfResult.target == target)\
        .order_by(IperfResult.timestamp.desc())\
        .limit(limit)\
        .all()

    return [
        {
            "id": result.id,
            "timestamp": result.timestamp,
            "target": result.target,
            "raw_output": result.raw_output,
            "parsed_metrics": json.loads(result.parsed_metrics) if result.parsed_metrics else {}
        }
        for result in results
    ]

def get_all_history(db: Session, tool: str, target: str, limit: int = 10):
    """Get history for any tool type."""
    if tool.lower() == "ping":
        return get_ping_history(db, target, limit)
    elif tool.lower() == "traceroute":
        return get_traceroute_history(db, target, limit)
    elif tool.lower() == "iperf":
        return get_iperf_history(db, target, limit)
    else:
        return []
