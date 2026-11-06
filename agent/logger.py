"""
Agent Logger — Observability Module
Logs every agent run with timestamps, tools called, latency, errors.
Stored in .logs/ for audit trail and debugging.
"""

import json
import os
from datetime import datetime
from typing import Optional

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".logs")
LOG_FILE = os.path.join(LOG_DIR, "agent_runs.jsonl")


def _ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)


def log_agent_run(
    query: str,
    response: str,
    tools_used: list,
    metadata: dict,
    broker_name: Optional[str] = None,
    error: Optional[str] = None,
):
    """
    Log an agent run to the JSONL log file.
    
    Each line is a JSON object representing one agent invocation.
    """
    _ensure_log_dir()
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "query": query[:200],  # Truncate long queries
        "response_length": len(response),
        "tools_used": [t.get("tool", "unknown") for t in tools_used],
        "tool_count": len(tools_used),
        "model": metadata.get("model", "unknown"),
        "region": metadata.get("region", "unknown"),
        "elapsed_seconds": metadata.get("elapsed_seconds", 0),
        "iterations": metadata.get("iterations", 0),
        "broker": broker_name,
        "error": error,
        "success": error is None,
    }
    
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


def get_run_stats() -> dict:
    """
    Get summary statistics from the log file.
    
    Returns:
        Dict with total runs, avg latency, tool usage counts, error rate
    """
    _ensure_log_dir()
    
    if not os.path.exists(LOG_FILE):
        return {"total_runs": 0, "message": "No runs logged yet"}
    
    runs = []
    try:
        with open(LOG_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    runs.append(json.loads(line))
    except (json.JSONDecodeError, IOError):
        return {"total_runs": 0, "error": "Log file corrupted"}
    
    if not runs:
        return {"total_runs": 0}
    
    # Calculate stats
    total = len(runs)
    successful = sum(1 for r in runs if r.get("success", False))
    total_latency = sum(r.get("elapsed_seconds", 0) for r in runs)
    
    # Tool usage frequency
    tool_counts = {}
    for run in runs:
        for tool in run.get("tools_used", []):
            tool_counts[tool] = tool_counts.get(tool, 0) + 1
    
    # Most common queries (word frequency)
    models_used = {}
    for run in runs:
        model = run.get("model", "unknown")
        models_used[model] = models_used.get(model, 0) + 1
    
    return {
        "total_runs": total,
        "successful_runs": successful,
        "failed_runs": total - successful,
        "success_rate_pct": round((successful / total) * 100, 1),
        "avg_latency_seconds": round(total_latency / total, 2),
        "avg_tools_per_run": round(sum(r.get("tool_count", 0) for r in runs) / total, 1),
        "tool_usage": dict(sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)),
        "models_used": models_used,
        "first_run": runs[0].get("timestamp", "unknown"),
        "last_run": runs[-1].get("timestamp", "unknown"),
    }


def get_recent_runs(n: int = 10) -> list:
    """Get the N most recent agent runs."""
    _ensure_log_dir()
    
    if not os.path.exists(LOG_FILE):
        return []
    
    runs = []
    try:
        with open(LOG_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    runs.append(json.loads(line))
    except (json.JSONDecodeError, IOError):
        return []
    
    return runs[-n:]
