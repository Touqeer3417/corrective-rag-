"""Production-grade caching layer with Redis primary + in-memory fallback."""

import hashlib
import json
import os
import pickle
from functools import wraps
from typing import Any, Callable, List, Optional, Union

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger("core.cache")

try:
    from cachetools import TTLCache
except ImportError:
    TTLCache = None

try:
    import redis
except ImportError:
    redis = None


class _NumpyEncoder(json.JSONEncoder):
    """Handle numpy types in JSON serialization."""
    def default(self, obj):
        try:
            import numpy as np
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, (np.integer, np.floating)):
                return obj.item()
        except ImportError:
            pass
        return super().default(obj)


def _make_key(*args, **kwargs) -> str:
    """Create deterministic hash key from arguments."""
    # Sort kwargs for consistency
    key_data = {
        "args": args,
        "kwargs": {k: v for k, v in sorted(kwargs.items())}
    }
    # Use pickle for complex objects, then hash
    try:
        raw = pickle.dumps(key_data, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        raw = json.dumps(key_data, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _serialize(value: Any) -> str:
    """Serialize value to string for cache storage."""
    try:
        return json.dumps(value, cls=_NumpyEncoder)
    except (TypeError, ValueError):
        # Fallback to pickle + base64 for complex objects
        import base64
        return "pickle:" + base64.b64encode(pickle.dumps(value)).decode()


def _deserialize(data: str) -> Any:
    """Deserialize cached string back to Python object."""
    if isinstance(data, bytes):
        data = data.decode()
    if data.startswith("pickle:"):
        import base64
        return pickle.loads(base64.b64decode(data[7:]))
    return json.loads(data)


class CacheManager:
    """Unified cache with Redis primary and in-memory fallback."""
    
    # In-memory fallback caches (class-level singletons)
    _memory_caches = {}
    
    def __init__(self, name: str, ttl_seconds: int = 3600, maxsize: int = 10000):
        self.name = name
        self.ttl = ttl_seconds
        self.maxsize = maxsize
        self._redis: Optional[Any] = None
        self._memory: Optional[Any] = None
        self._init_cache()
    
    def _init_cache(self):
        settings = get_settings()
        redis_url = getattr(settings, "redis_url", None) or os.getenv("REDIS_URL")
        
        # Try Redis first
        if redis and redis_url:
            try:
                self._redis = redis.from_url(
                    redis_url,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                    decode_responses=True
                )
                self._redis.ping()
                logger.info(f"[CACHE] Redis connected for '{self.name}'")
                return
            except Exception as e:
                logger.warning(f"[CACHE] Redis failed for '{self.name}': {e}. Using memory fallback.")
                self._redis = None
        
        # Fallback to in-memory TTL cache
        if TTLCache:
            cache_key = f"{self.name}:{self.ttl}:{self.maxsize}"
            if cache_key not in CacheManager._memory_caches:
                CacheManager._memory_caches[cache_key] = TTLCache(
                    maxsize=self.maxsize, 
                    ttl=self.ttl
                )
            self._memory = CacheManager._memory_caches[cache_key]
            logger.info(f"[CACHE] In-memory TTL cache active for '{self.name}' (ttl={self.ttl}s)")
        else:
            logger.warning(f"[CACHE] No caching available! Install redis or cachetools.")
    
    def _prefixed_key(self, key: str) -> str:
        return f"crag:{self.name}:{key}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            if self._redis:
                data = self._redis.get(self._prefixed_key(key))
                if data is not None:
                    return _deserialize(data)
                return None
            
            if self._memory:
                return self._memory.get(key)
            
            return None
        except Exception as e:
            logger.warning(f"[CACHE] Get error for '{self.name}': {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        try:
            serialized = _serialize(value)
            effective_ttl = ttl or self.ttl
            
            if self._redis:
                self._redis.setex(
                    self._prefixed_key(key), 
                    effective_ttl, 
                    serialized
                )
                return True
            
            if self._memory:
                self._memory[key] = value
                return True
            
            return False
        except Exception as e:
            logger.warning(f"[CACHE] Set error for '{self.name}': {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            if self._redis:
                self._redis.delete(self._prefixed_key(key))
                return True
            if self._memory and key in self._memory:
                del self._memory[key]
                return True
            return False
        except Exception as e:
            logger.warning(f"[CACHE] Delete error: {e}")
            return False
    
    def clear(self) -> bool:
        """Clear all keys for this cache namespace."""
        try:
            if self._redis:
                pattern = self._prefixed_key("*")
                for key in self._redis.scan_iter(match=pattern):
                    self._redis.delete(key)
                return True
            if self._memory:
                self._memory.clear()
                return True
            return False
        except Exception as e:
            logger.warning(f"[CACHE] Clear error: {e}")
            return False


# Singleton cache instances per layer
_embedding_cache: Optional[CacheManager] = None
_retrieval_cache: Optional[CacheManager] = None
_grade_cache: Optional[CacheManager] = None
_answer_cache: Optional[CacheManager] = None


def get_embedding_cache() -> CacheManager:
    global _embedding_cache
    if _embedding_cache is None:
        settings = get_settings()
        _embedding_cache = CacheManager(
            name="embedding",
            ttl_seconds=getattr(settings, "cache_embedding_ttl", 86400),  # 24h
            maxsize=50000
        )
    return _embedding_cache


def get_retrieval_cache() -> CacheManager:
    global _retrieval_cache
    if _retrieval_cache is None:
        settings = get_settings()
        _retrieval_cache = CacheManager(
            name="retrieval",
            ttl_seconds=getattr(settings, "cache_retrieval_ttl", 3600),  # 1h
            maxsize=10000
        )
    return _retrieval_cache


def get_grade_cache() -> CacheManager:
    global _grade_cache
    if _grade_cache is None:
        settings = get_settings()
        _grade_cache = CacheManager(
            name="grade",
            ttl_seconds=getattr(settings, "cache_grade_ttl", 3600),  # 1h
            maxsize=5000
        )
    return _grade_cache


def get_answer_cache() -> CacheManager:
    global _answer_cache
    if _answer_cache is None:
        settings = get_settings()
        _answer_cache = CacheManager(
            name="answer",
            ttl_seconds=getattr(settings, "cache_answer_ttl", 1800),  # 30m
            maxsize=5000
        )
    return _answer_cache


def cached(cache_manager_fn: Callable[[], CacheManager], key_fn: Optional[Callable] = None):
    """Decorator to cache function results."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = cache_manager_fn()
            
            # Build cache key
            if key_fn:
                cache_key = key_fn(*args, **kwargs)
            else:
                cache_key = _make_key(func.__name__, *args, **kwargs)
            
            # Try cache hit
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"[CACHE] HIT for {func.__name__}")
                return cached_value
            
            # Cache miss - compute
            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            logger.debug(f"[CACHE] MISS for {func.__name__} - stored")
            return result
        
        # Attach cache clear method
        wrapper.cache_clear = lambda: cache_manager_fn().clear()
        return wrapper
    return decorator