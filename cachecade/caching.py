import os
import time
import hashlib
import json
from functools import wraps
from flask import jsonify, Response

# Try importing Replit DB.
try:
    from replit import db as replit_db
except ImportError:
    replit_db = None

# Globals to hold caching backend state.
redis_client = None
memory_store = {}  # In-memory store for caching.
cache_backend = None  # Will be set to one of 'redis', 'replit', or 'memory'.
cache_prefix = None   # Optional prefix for cache keys

def init_cache(storage_engines=None, prefix=None):
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
                    print("Using Redis for caching.")
                    return
                except ImportError:
                    print("Redis engine selected but the 'redis' module is not installed. Skipping Redis.")
            else:
                print("Redis engine specified but 'REDIS_URL' is not defined. Skipping Redis.")
        elif engine == 'replit':
            if replit_db is not None:
                cache_backend = 'replit'
                print("Using Replit key–value store for caching.")
                return
            else:
                print("Replit engine selected, but the replit module is not available. Skipping Replit.")
        elif engine == 'memory':
            cache_backend = 'memory'
            memory_store = {}  # Reset in-memory store.
            print("Using in-memory caching.")
            return
        else:
            print(f"Unknown storage engine '{engine}'. Skipping.")
    print("No valid caching backend selected. Please check your configuration.")

def generate_cache_key(func_name, args, kwargs):
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

def get_cache_entry(key):
    """Retrieve the cache entry for a given key using the chosen backend."""
    if cache_backend == 'redis' and redis_client:
        entry = redis_client.get(key)
        return entry.decode('utf-8') if entry else None
    elif cache_backend == 'replit' and replit_db:
        return replit_db.get(key)
    elif cache_backend == 'memory':
        return memory_store.get(key)
    return None

def set_cache_entry(key, value, ttl=None):
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

def replit_cached(ttl=60):
    """
    Decorator to cache function results using the active backend (Redis, Replit DB, or in-memory).
    
    Parameters:
        ttl (int): Time-to-live in seconds for cache entries
    
    The cached result is stored along with a timestamp and returned as a JSON response if valid.
    Uses the global cache prefix if one was set during initialization.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = generate_cache_key(func.__name__, args, kwargs)
            cache_entry = get_cache_entry(cache_key)
            if cache_entry:
                timestamp, data = json.loads(cache_entry)
                if (time.time() - timestamp) < ttl:
                    print(f"Using cached data for {func.__name__} from {cache_backend}.")
                    return jsonify(data)
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
            return jsonify(result_data)
        return wrapper
    return decorator
