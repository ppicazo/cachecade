import os
import time
import hashlib
import json
import logging
from functools import wraps
from typing import Optional, List, Any, Union, Dict, Tuple, Callable
from flask import jsonify, Response

# Configure logger for cachecade
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Try importing Replit DB.
try:
    from replit import db as replit_db
except ImportError:
    replit_db = None

# Globals to hold caching backend state.
redis_client: Optional[Any] = None
memory_store: Dict[str, str] = {}  # In-memory store for caching.
cache_backend: Optional[str] = None  # Will be set to one of 'redis', 'replit', or 'memory'.
cache_prefix: Optional[str] = None   # Optional prefix for cache keys

def init_cache(storage_engines: Optional[List[str]] = None, prefix: Optional[str] = None) -> None:
    """
    Initialize the caching backend based on the provided list of storage engines.
    
    Parameters:
        storage_engines (list): A prioritized list of storage engine names.
                                Available options: 'redis', 'replit', 'memory'.
                                Default is ['replit', 'redis', 'memory'].
        prefix (str, optional): Optional prefix to prepend to all cache keys.
                                This can be used to namespace cache keys.
    
    Behavior:
      - If 'replit' is specified first and is available, it will use the Replit key–value store.
      - Next, if 'redis' is specified, it checks for the REDIS_URL environment variable and attempts a connection.
      - Finally, if 'memory' is specified or if previous backends are unavailable, it uses in-memory caching.
    
      The list order controls precedence.
    """
    global redis_client, cache_backend, memory_store, cache_prefix

    # Set the global cache prefix
    cache_prefix = prefix

    if storage_engines is None:
        storage_engines = ['replit', 'redis', 'memory']

    for engine in storage_engines:
        engine = engine.lower().strip()
        if engine == 'redis':
            redis_url = os.environ.get('REDIS_URL')
            if redis_url:
                try:
                    import redis  # Import redis library.
                    redis_client = redis.from_url(redis_url)
                    cache_backend = 'redis'
                    logger.info("Using Redis for caching.")
                    return
                except ImportError:
                    logger.warning("Redis engine selected but the 'redis' module is not installed. Skipping Redis.")
            else:
                logger.warning("Redis engine specified but 'REDIS_URL' is not defined. Skipping Redis.")
        elif engine == 'replit':
            if replit_db is not None:
                cache_backend = 'replit'
                logger.info("Using Replit key–value store for caching.")
                return
            else:
                logger.warning("Replit engine selected, but the replit module is not available. Skipping Replit.")
        elif engine == 'memory':
            cache_backend = 'memory'
            memory_store = {}  # Reset in-memory store.
            logger.info("Using in-memory caching.")
            return
        else:
            logger.warning(f"Unknown storage engine '{engine}'. Skipping.")
    logger.error("No valid caching backend selected. Please check your configuration.")

def generate_cache_key(func_name: str, args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> str:
    """Generate a unique cache key for the given function and its arguments.
    
    Parameters:
        func_name (str): The name of the function being cached
        args (tuple): Positional arguments passed to the function
        kwargs (dict): Keyword arguments passed to the function
    
    Returns:
        str: A SHA256 hexadecimal hash that serves as the cache key
    """
    # Add global prefix if available
    key_base = f"{cache_prefix}:" if cache_prefix else ""
    key_base += f"{func_name}_{args}_{kwargs}"
    key_data = key_base.encode('utf-8')
    return hashlib.sha256(key_data).hexdigest()

def get_cache_entry(key: str) -> Optional[str]:
    """Retrieve the cache entry for a given key using the chosen backend."""
    if cache_backend == 'redis' and redis_client:
        entry = redis_client.get(key)
        return entry.decode('utf-8') if entry else None
    elif cache_backend == 'replit' and replit_db:
        entry = replit_db.get(key)
        if entry:
            # Check if entry has expired for Replit backend
            try:
                timestamp, data = json.loads(entry)
                # Note: We can't know TTL here, so we return the entry and let the decorator check
                return entry
            except (json.JSONDecodeError, ValueError):
                return entry  # Legacy entry format
        return None
    elif cache_backend == 'memory':
        entry = memory_store.get(key)
        if entry:
            # Check if entry has expired for memory backend
            try:
                timestamp, data = json.loads(entry)
                # Note: We can't know TTL here, so we return the entry and let the decorator check
                return entry
            except (json.JSONDecodeError, ValueError):
                return entry  # Legacy entry format
        return None
    return None

def set_cache_entry(key: str, value: str, ttl: Optional[int] = None) -> None:
    """
    Store the cache entry for a given key using the chosen backend.
    
    For Redis, TTL (time-to-live) is handled via the setex command.
    For the Replit and in-memory backends, TTL checking is managed within the decorator.
    """
    if cache_backend == 'redis' and redis_client:
        if ttl:
            redis_client.setex(key, ttl, value)
        else:
            redis_client.set(key, value)
    elif cache_backend == 'replit' and replit_db:
        replit_db[key] = value
    elif cache_backend == 'memory':
        memory_store[key] = value

def clear_cache(pattern: Optional[str] = None) -> None:
    """
    Clear cache entries. 
    
    Parameters:
        pattern (str, optional): If provided, only clear keys matching this pattern.
                                For memory backend, this does a simple string containment check.
                                For Redis, this uses the KEYS command (use with caution in production).
                                For Replit, this iterates through all keys.
    """
    if cache_backend == 'redis' and redis_client:
        if pattern:
            # Use SCAN for better performance in production
            keys = []
            cursor = 0
            while True:
                cursor, partial_keys = redis_client.scan(cursor=cursor, match=pattern)
                keys.extend(partial_keys)
                if cursor == 0:
                    break
            if keys:
                redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} Redis cache entries matching pattern '{pattern}'")
        else:
            redis_client.flushdb()
            logger.info("Cleared all Redis cache entries")
    elif cache_backend == 'replit' and replit_db:
        keys_to_delete = []
        try:
            # Get all keys and filter by pattern if provided
            for key in replit_db.keys():
                if pattern is None or pattern in key:
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del replit_db[key]
            logger.info(f"Cleared {len(keys_to_delete)} Replit cache entries" + 
                       (f" matching pattern '{pattern}'" if pattern else ""))
        except Exception as e:
            logger.error(f"Error clearing Replit cache: {e}")
    elif cache_backend == 'memory':
        if pattern:
            keys_to_delete = [key for key in memory_store.keys() if pattern in key]
            for key in keys_to_delete:
                del memory_store[key]
            logger.info(f"Cleared {len(keys_to_delete)} memory cache entries matching pattern '{pattern}'")
        else:
            count = len(memory_store)
            memory_store.clear()
            logger.info(f"Cleared {count} memory cache entries")
    else:
        logger.warning("No cache backend available for clearing")

def invalidate_cache_key(func_name: str, args: Tuple[Any, ...] = (), kwargs: Optional[Dict[str, Any]] = None) -> bool:
    """
    Invalidate a specific cache key.
    
    Parameters:
        func_name (str): The name of the function whose cache should be invalidated
        args (tuple): The positional arguments used when the function was called
        kwargs (dict): The keyword arguments used when the function was called
    """
    if kwargs is None:
        kwargs = {}
    
    cache_key = generate_cache_key(func_name, args, kwargs)
    
    if cache_backend == 'redis' and redis_client:
        result = redis_client.delete(cache_key)
        if result:
            logger.debug(f"Invalidated Redis cache key for {func_name}")
        return result > 0
    elif cache_backend == 'replit' and replit_db:
        try:
            del replit_db[cache_key]
            logger.debug(f"Invalidated Replit cache key for {func_name}")
            return True
        except KeyError:
            return False
    elif cache_backend == 'memory':
        result = memory_store.pop(cache_key, None)
        if result is not None:
            logger.debug(f"Invalidated memory cache key for {func_name}")
        return result is not None
    
    return False

def cachecaded(ttl: int = 60, return_json: bool = True) -> Callable[[Callable], Callable]:
    """
    Decorator to cache function results using the active backend (Redis, Replit DB, or in-memory).
    
    Parameters:
        ttl (int): Time-to-live in seconds for cache entries
        return_json (bool): If True, automatically wrap result in jsonify(). 
                           If False, return the raw cached data or function result.
    
    The cached result is stored along with a timestamp and returned as a JSON response if valid.
    Uses the global cache prefix if one was set during initialization.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            cache_key = generate_cache_key(func.__name__, args, kwargs)
            cache_entry = get_cache_entry(cache_key)
            if cache_entry:
                try:
                    timestamp, data = json.loads(cache_entry)
                    if (time.time() - timestamp) < ttl:
                        logger.debug(f"Using cached data for {func.__name__} from {cache_backend}.")
                        return jsonify(data) if return_json else data
                    else:
                        # Entry has expired, remove it for non-Redis backends
                        if cache_backend == 'replit' and replit_db:
                            try:
                                del replit_db[cache_key]
                                logger.debug(f"Expired cache entry removed from Replit for {func.__name__}")
                            except KeyError:
                                pass  # Entry already removed
                        elif cache_backend == 'memory':
                            memory_store.pop(cache_key, None)
                            logger.debug(f"Expired cache entry removed from memory for {func.__name__}")
                except (json.JSONDecodeError, ValueError):
                    # Invalid cache entry, remove it
                    if cache_backend == 'replit' and replit_db:
                        try:
                            del replit_db[cache_key]
                        except KeyError:
                            pass
                    elif cache_backend == 'memory':
                        memory_store.pop(cache_key, None)
            
            result = func(*args, **kwargs)
            if isinstance(result, Response):
                result_data = result.get_json()
            else:
                result_data = result
            entry = json.dumps((time.time(), result_data))
            if cache_backend == 'redis':
                set_cache_entry(cache_key, entry, ttl=ttl)
            else:
                set_cache_entry(cache_key, entry)
            return jsonify(result_data) if return_json else result_data
        return wrapper
    return decorator
