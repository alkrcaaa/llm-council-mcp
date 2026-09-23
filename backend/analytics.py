"""Analytics storage and aggregation for model performance tracking."""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import defaultdict

from .config import DATA_ROOT

# Analytics data directory
ANALYTICS_DIR = os.path.join(DATA_ROOT, "analytics")
ANALYTICS_FILE = os.path.join(ANALYTICS_DIR, "model_stats.json")


def ensure_analytics_dir():
    """Ensure the analytics directory exists."""
    Path(ANALYTICS_DIR).mkdir(parents=True, exist_ok=True)


def load_analytics() -> Dict[str, Any]:
    """
    Load analytics data from storage.

    Returns:
        Dict containing analytics data with structure:
        {
            "queries": [...],  # List of individual query records
            "last_updated": "ISO timestamp"
        }
    """
    ensure_analytics_dir()

    if not os.path.exists(ANALYTICS_FILE):
        return {"queries": [], "last_updated": None}

    try:
        with open(ANALYTICS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"queries": [], "last_updated": None}


def save_analytics(data: Dict[str, Any]):
    """
    Save analytics data to storage.

    Args:
        data: Analytics data dict to save
    """
    ensure_analytics_dir()

    data["last_updated"] = datetime.utcnow().isoformat()

    with open(ANALYTICS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def record_query_result(
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    stage3_result: Dict[str, Any],
    aggregate_rankings: List[Dict[str, Any]],
    query_duration_ms: Optional[float] = None
):
    """
    Record the results of a council query for analytics.

    This records:
    - Which models participated
    - Their ranking positions (from aggregate rankings)
    - Response confidence scores
    - Cost data
    - Timing information

    Args:
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2
        stage3_result: Final synthesis from Stage 3
        aggregate_rankings: Calculated aggregate rankings
        query_duration_ms: Optional total query duration in milliseconds
    """
    analytics = load_analytics()

    # Build model performance entries
    model_performances = []

    for result in stage1_results:
        model = result.get("model")
        if not model:
            continue

        # Find this model's aggregate ranking
        ranking_entry = next(
            (r for r in aggregate_rankings if r.get("model") == model),
            None
        )

        performance = {
            "model": model,
            "confidence": result.get("confidence"),
            "rank_position": ranking_entry.get("average_rank") if ranking_entry else None,
            "was_top_ranked": ranking_entry.get("average_rank", 999) <= 1.5 if ranking_entry else False,
            "cost": result.get("cost", {}),
            "usage": result.get("usage", {}),
        }
        model_performances.append(performance)

    # Create query record
    query_record = {
        "timestamp": datetime.utcnow().isoformat(),
        "models": model_performances,
        "chairman_model": stage3_result.get("model"),
        "chairman_cost": stage3_result.get("cost", {}),
        "total_models": len(stage1_results),
        "query_duration_ms": query_duration_ms,
    }

    analytics["queries"].append(query_record)
    save_analytics(analytics)


def get_model_statistics() -> Dict[str, Any]:
    """
    Calculate aggregate statistics for all models.

    Returns:
        Dict with model statistics:
        {
            "models": {
                "model_name": {
                    "total_queries": int,
                    "wins": int,  # Times ranked #1 (avg rank <= 1.5)
                    "win_rate": float,  # Percentage
                    "average_rank": float,
                    "average_confidence": float,
                    "total_cost": float,
                    "total_tokens": int,
                    "rank_distribution": {1: count, 2: count, ...}
                },
                ...
            },
            "summary": {
                "total_queries": int,
                "unique_models": int,
                "date_range": {"start": str, "end": str}
            }
        }
    """
    analytics = load_analytics()
    queries = analytics.get("queries", [])

    if not queries:
        return {
            "models": {},
            "summary": {
                "total_queries": 0,
                "unique_models": 0,
                "date_range": None
            }
        }

    # Aggregate model stats
    model_stats = defaultdict(lambda: {
        "total_queries": 0,
        "wins": 0,
        "rank_positions": [],
        "confidences": [],
        "total_cost": 0.0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "rank_distribution": defaultdict(int),
    })

    for query in queries:
        for model_perf in query.get("models", []):
            model = model_perf.get("model")
            if not model:
                continue

            stats = model_stats[model]
            stats["total_queries"] += 1

            # Track wins
            if model_perf.get("was_top_ranked"):
                stats["wins"] += 1

            # Track rank positions
            rank = model_perf.get("rank_position")
            if rank is not None:
                stats["rank_positions"].append(rank)
                # Round to nearest int for distribution
                rounded_rank = round(rank)
                stats["rank_distribution"][rounded_rank] += 1

            # Track confidence
            confidence = model_perf.get("confidence")
            if confidence is not None:
                stats["confidences"].append(confidence)

            # Track costs
            cost = model_perf.get("cost", {})
            stats["total_cost"] += cost.get("total", 0)

            # Track tokens
            usage = model_perf.get("usage", {})
            stats["total_prompt_tokens"] += usage.get("prompt_tokens", 0)
            stats["total_completion_tokens"] += usage.get("completion_tokens", 0)

    # Calculate final statistics
    result_models = {}
    for model, stats in model_stats.items():
        total_queries = stats["total_queries"]
        result_models[model] = {
            "total_queries": total_queries,
            "wins": stats["wins"],
            "win_rate": round((stats["wins"] / total_queries) * 100, 1) if total_queries > 0 else 0,
            "average_rank": round(sum(stats["rank_positions"]) / len(stats["rank_positions"]), 2) if stats["rank_positions"] else None,
            "average_confidence": round(sum(stats["confidences"]) / len(stats["confidences"]), 1) if stats["confidences"] else None,
            "total_cost": round(stats["total_cost"], 4),
            "total_tokens": stats["total_prompt_tokens"] + stats["total_completion_tokens"],
            "total_prompt_tokens": stats["total_prompt_tokens"],
            "total_completion_tokens": stats["total_completion_tokens"],
            "rank_distribution": dict(sorted(stats["rank_distribution"].items())),
        }

    # Sort models by win rate (descending)
    result_models = dict(sorted(
        result_models.items(),
        key=lambda x: (
            x[1]["win_rate"],
            -(x[1].get("average_rank") if x[1].get("average_rank") is not None else 999)
        ),
        reverse=True
    ))

    # Build summary
    timestamps = [q.get("timestamp") for q in queries if q.get("timestamp")]
    summary = {
        "total_queries": len(queries),
        "unique_models": len(result_models),
        "date_range": {
            "start": min(timestamps) if timestamps else None,
            "end": max(timestamps) if timestamps else None,
        }
    }

    return {
        "models": result_models,
        "summary": summary
    }


def get_recent_queries(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get the most recent query records.

    Args:
        limit: Maximum number of queries to return

    Returns:
        List of recent query records, newest first
    """
    analytics = load_analytics()
    queries = analytics.get("queries", [])

    # Sort by timestamp descending and return limited results
    sorted_queries = sorted(
        queries,
        key=lambda x: x.get("timestamp", ""),
        reverse=True
    )

    return sorted_queries[:limit]


def get_chairman_statistics() -> Dict[str, Any]:
    """
    Get statistics about chairman model usage.

    Returns:
        Dict with chairman statistics:
        {
            "models": {
                "model_name": {
                    "times_used": int,
                    "total_cost": float,
                    "total_tokens": int
                },
                ...
            },
            "total_syntheses": int
        }
    """
    analytics = load_analytics()
    queries = analytics.get("queries", [])

    chairman_stats = defaultdict(lambda: {
        "times_used": 0,
        "total_cost": 0.0,
        "total_tokens": 0,
    })

    for query in queries:
        chairman = query.get("chairman_model")
        if chairman:
            stats = chairman_stats[chairman]
            stats["times_used"] += 1

            cost = query.get("chairman_cost", {})
            stats["total_cost"] += cost.get("total", 0)

    # Convert to regular dict and round costs
    result = {}
    for model, stats in chairman_stats.items():
        result[model] = {
            "times_used": stats["times_used"],
            "total_cost": round(stats["total_cost"], 4),
        }

    return {
        "models": dict(sorted(result.items(), key=lambda x: x[1]["times_used"], reverse=True)),
        "total_syntheses": len(queries)
    }


def clear_analytics():
    """
    Clear all analytics data.

    Use with caution - this permanently deletes all recorded statistics.
    """
    ensure_analytics_dir()

    if os.path.exists(ANALYTICS_FILE):
        os.remove(ANALYTICS_FILE)
