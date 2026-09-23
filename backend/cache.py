"""Semantic response caching for LLM Council.

This module provides a semantic cache that stores question-answer pairs
with embeddings. When a similar question is asked, the cached response
is returned instead of re-querying all the models, saving time and cost.

Cache entries include:
- Original query text
- Query embedding vector
- Full council response (stage1, stage2, stage3, metadata)
- Timestamp and usage statistics
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

from .config import DATA_ROOT

from .embeddings import (
    get_embedding_with_fallback,
    cosine_similarity,
    find_most_similar,
    DEFAULT_EMBEDDING_MODEL
)

# Cache storage directory
CACHE_DIR = os.path.join(DATA_ROOT, "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "semantic_cache.json")
CACHE_STATS_FILE = os.path.join(CACHE_DIR, "cache_stats.json")

# Default configuration
DEFAULT_SIMILARITY_THRESHOLD = 0.92  # High threshold for quality matches
DEFAULT_MAX_CACHE_ENTRIES = 1000  # Maximum number of cached entries
DEFAULT_USE_API_EMBEDDINGS = True  # Use OpenAI embeddings by default


def ensure_cache_dir():
    """Ensure the cache directory exists."""
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)


def load_cache() -> Dict[str, Any]:
    """
    Load cache data from storage.

    Returns:
        Dict containing cache data with structure:
        {
            "entries": [...],  # List of cached query-response pairs
            "last_updated": "ISO timestamp"
        }
    """
    ensure_cache_dir()

    if not os.path.exists(CACHE_FILE):
        return {"entries": [], "last_updated": None}

    try:
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"entries": [], "last_updated": None}


def save_cache(data: Dict[str, Any]):
    """
    Save cache data to storage.

    Args:
        data: Cache data dict to save
    """
    ensure_cache_dir()

    data["last_updated"] = datetime.utcnow().isoformat()

    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def load_cache_stats() -> Dict[str, Any]:
    """
    Load cache statistics from storage.

    Returns:
        Dict containing cache statistics
    """
    ensure_cache_dir()

    if not os.path.exists(CACHE_STATS_FILE):
        return {
            "total_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_cost_saved": 0.0,
            "total_time_saved_ms": 0,
            "hit_rate": 0.0,
            "last_updated": None
        }

    try:
        with open(CACHE_STATS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {
            "total_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_cost_saved": 0.0,
            "total_time_saved_ms": 0,
            "hit_rate": 0.0,
            "last_updated": None
        }


def save_cache_stats(stats: Dict[str, Any]):
    """
    Save cache statistics to storage.

    Args:
        stats: Statistics dict to save
    """
    ensure_cache_dir()

    # Calculate hit rate
    if stats.get("total_queries", 0) > 0:
        stats["hit_rate"] = stats.get("cache_hits", 0) / stats["total_queries"]
    else:
        stats["hit_rate"] = 0.0

    stats["last_updated"] = datetime.utcnow().isoformat()

    with open(CACHE_STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=2)


def record_cache_hit(cost_saved: float = 0.0, time_saved_ms: int = 0):
    """
    Record a cache hit in statistics.

    Args:
        cost_saved: Estimated cost saved by cache hit (USD)
        time_saved_ms: Estimated time saved by cache hit (milliseconds)
    """
    stats = load_cache_stats()
    stats["total_queries"] = stats.get("total_queries", 0) + 1
    stats["cache_hits"] = stats.get("cache_hits", 0) + 1
    stats["total_cost_saved"] = stats.get("total_cost_saved", 0.0) + cost_saved
    stats["total_time_saved_ms"] = stats.get("total_time_saved_ms", 0) + time_saved_ms
    save_cache_stats(stats)


def record_cache_miss():
    """Record a cache miss in statistics."""
    stats = load_cache_stats()
    stats["total_queries"] = stats.get("total_queries", 0) + 1
    stats["cache_misses"] = stats.get("cache_misses", 0) + 1
    save_cache_stats(stats)


async def add_cache_entry(
    query: str,
    response: Dict[str, Any],
    system_prompt: Optional[str] = None,
    use_api_embeddings: bool = DEFAULT_USE_API_EMBEDDINGS,
    max_entries: int = DEFAULT_MAX_CACHE_ENTRIES
) -> Dict[str, Any]:
    """
    Add a new entry to the cache.

    Args:
        query: The user's question
        response: The full council response (stage1, stage2, stage3, metadata)
        system_prompt: Optional system prompt (affects cache key)
        use_api_embeddings: Whether to use API embeddings or hash fallback
        max_entries: Maximum cache entries (evicts oldest if exceeded)

    Returns:
        Dict with cache entry details
    """
    # Generate embedding for the query
    embedding_result = await get_embedding_with_fallback(
        query,
        use_api=use_api_embeddings
    )

    # Create cache entry
    entry = {
        "id": datetime.utcnow().isoformat() + "-" + str(hash(query) % 10000),
        "query": query,
        "system_prompt": system_prompt,
        "embedding": embedding_result['embedding'],
        "embedding_method": embedding_result['method'],
        "embedding_model": embedding_result['model'],
        "response": response,
        "created_at": datetime.utcnow().isoformat(),
        "hit_count": 0,
        "last_hit": None
    }

    # Load existing cache
    cache = load_cache()

    # Add new entry
    cache["entries"].append(entry)

    # Enforce max entries limit (evict oldest entries)
    if len(cache["entries"]) > max_entries:
        # Sort by created_at and keep only the newest entries
        cache["entries"].sort(key=lambda x: x.get("created_at", ""), reverse=True)
        cache["entries"] = cache["entries"][:max_entries]

    # Save updated cache
    save_cache(cache)

    return {
        "id": entry["id"],
        "query": query,
        "embedding_method": embedding_result['method'],
        "cache_size": len(cache["entries"])
    }


async def search_cache(
    query: str,
    system_prompt: Optional[str] = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    use_api_embeddings: bool = DEFAULT_USE_API_EMBEDDINGS
) -> Optional[Dict[str, Any]]:
    """
    Search the cache for a similar query.

    Args:
        query: The user's question to search for
        system_prompt: Optional system prompt (must match for cache hit)
        similarity_threshold: Minimum similarity score for a match
        use_api_embeddings: Whether to use API embeddings or hash fallback

    Returns:
        Dict with cached response if found, None otherwise.
        Includes: response, similarity, cached_query, cache_id
    """
    # Load cache
    cache = load_cache()

    if not cache.get("entries"):
        return None

    # Generate embedding for the query
    embedding_result = await get_embedding_with_fallback(
        query,
        use_api=use_api_embeddings
    )
    query_embedding = embedding_result['embedding']

    # Filter by system_prompt if provided
    # If system_prompt is specified, only match entries with same system_prompt
    filtered_entries = []
    for entry in cache["entries"]:
        entry_system_prompt = entry.get("system_prompt")
        # Match if both are None or both are the same string
        if system_prompt == entry_system_prompt:
            filtered_entries.append(entry)
        # Also match if both are empty/None (for backwards compatibility)
        elif not system_prompt and not entry_system_prompt:
            filtered_entries.append(entry)

    if not filtered_entries:
        return None

    # Find best match
    best_match = None
    best_score = similarity_threshold

    for entry in filtered_entries:
        stored_embedding = entry.get("embedding", [])

        # Skip if embedding dimensions don't match
        if len(stored_embedding) != len(query_embedding):
            continue

        similarity = cosine_similarity(query_embedding, stored_embedding)

        if similarity > best_score:
            best_score = similarity
            best_match = entry

    if best_match:
        # Update hit statistics on the entry
        cache = load_cache()
        for entry in cache["entries"]:
            if entry.get("id") == best_match.get("id"):
                entry["hit_count"] = entry.get("hit_count", 0) + 1
                entry["last_hit"] = datetime.utcnow().isoformat()
                break
        save_cache(cache)

        return {
            "response": best_match.get("response"),
            "similarity": best_score,
            "cached_query": best_match.get("query"),
            "cache_id": best_match.get("id"),
            "created_at": best_match.get("created_at"),
            "hit_count": best_match.get("hit_count", 0) + 1
        }

    return None


def clear_cache() -> Dict[str, Any]:
    """
    Clear all cache entries.

    Returns:
        Dict with operation result
    """
    ensure_cache_dir()

    # Get entry count before clearing
    cache = load_cache()
    entries_cleared = len(cache.get("entries", []))

    # Clear cache
    save_cache({"entries": [], "last_updated": None})

    return {
        "success": True,
        "entries_cleared": entries_cleared,
        "message": f"Cleared {entries_cleared} cache entries"
    }


def clear_cache_stats() -> Dict[str, Any]:
    """
    Clear cache statistics.

    Returns:
        Dict with operation result
    """
    save_cache_stats({
        "total_queries": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "total_cost_saved": 0.0,
        "total_time_saved_ms": 0,
        "hit_rate": 0.0,
        "last_updated": None
    })

    return {
        "success": True,
        "message": "Cache statistics cleared"
    }


def get_cache_info() -> Dict[str, Any]:
    """
    Get cache information and statistics.

    Returns:
        Dict with cache info including size, stats, and config
    """
    cache = load_cache()
    stats = load_cache_stats()

    entries = cache.get("entries", [])

    # Calculate entry statistics
    total_hits = sum(e.get("hit_count", 0) for e in entries)
    api_embeddings = sum(1 for e in entries if e.get("embedding_method") == "api")
    hash_embeddings = sum(1 for e in entries if e.get("embedding_method") == "hash")

    return {
        "cache_size": len(entries),
        "max_entries": DEFAULT_MAX_CACHE_ENTRIES,
        "similarity_threshold": DEFAULT_SIMILARITY_THRESHOLD,
        "use_api_embeddings": DEFAULT_USE_API_EMBEDDINGS,
        "total_entry_hits": total_hits,
        "api_embedding_entries": api_embeddings,
        "hash_embedding_entries": hash_embeddings,
        "last_updated": cache.get("last_updated"),
        "stats": stats
    }


def delete_cache_entry(cache_id: str) -> Dict[str, Any]:
    """
    Delete a specific cache entry by ID.

    Args:
        cache_id: The ID of the cache entry to delete

    Returns:
        Dict with operation result
    """
    cache = load_cache()
    original_count = len(cache.get("entries", []))

    cache["entries"] = [
        e for e in cache.get("entries", [])
        if e.get("id") != cache_id
    ]

    if len(cache["entries"]) < original_count:
        save_cache(cache)
        return {
            "success": True,
            "deleted": cache_id,
            "message": f"Deleted cache entry {cache_id}"
        }
    else:
        return {
            "success": False,
            "message": f"Cache entry {cache_id} not found"
        }


def get_cache_entries(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """
    Get paginated list of cache entries.

    Args:
        limit: Maximum entries to return
        offset: Number of entries to skip

    Returns:
        Dict with entries and pagination info
    """
    cache = load_cache()
    entries = cache.get("entries", [])

    # Sort by created_at descending (newest first)
    entries.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    # Paginate
    total = len(entries)
    paginated = entries[offset:offset + limit]

    # Return entries without embeddings (too large for API response)
    cleaned_entries = []
    for entry in paginated:
        cleaned_entries.append({
            "id": entry.get("id"),
            "query": entry.get("query"),
            "system_prompt": entry.get("system_prompt"),
            "embedding_method": entry.get("embedding_method"),
            "created_at": entry.get("created_at"),
            "hit_count": entry.get("hit_count", 0),
            "last_hit": entry.get("last_hit"),
            # Include a preview of the response
            "response_preview": _get_response_preview(entry.get("response", {}))
        })

    return {
        "entries": cleaned_entries,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total
    }


def _get_response_preview(response: Dict[str, Any]) -> str:
    """
    Get a short preview of the response for display.

    Args:
        response: Full council response

    Returns:
        Short preview string
    """
    if not response:
        return ""

    # Try to get Stage 3 response preview
    stage3 = response.get("stage3", {})
    if isinstance(stage3, dict):
        text = stage3.get("response", "")
    else:
        text = str(stage3) if stage3 else ""

    # Truncate to first 150 characters
    if len(text) > 150:
        return text[:150] + "..."
    return text


def get_cache_config() -> Dict[str, Any]:
    """
    Get cache configuration for API endpoint.

    Returns:
        Dict with cache configuration details
    """
    return {
        "similarity_threshold": DEFAULT_SIMILARITY_THRESHOLD,
        "max_cache_entries": DEFAULT_MAX_CACHE_ENTRIES,
        "use_api_embeddings": DEFAULT_USE_API_EMBEDDINGS,
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "cache_dir": CACHE_DIR,
        "description": "Semantic response cache that stores and retrieves similar queries"
    }
