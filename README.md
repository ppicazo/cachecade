# Cachecade

**Cachecade** is a flexible caching package for Flask applications that supports multiple backends with a prioritized fallback mechanism. Out of the box, it supports:

- **Replit Key–Value Store**
- **Redis**
- **In-Memory Caching**

## Features

- **Prioritized Storage Engines:** By default, Cachecade uses `['replit', 'redis', 'memory']` as the order of precedence.
- **TTL Support:** Cache entries have a time-to-live (TTL) after which they are considered stale.
- **Decorator-Based Caching:** Easily cache function results by using the provided decorator.

## Installation

Clone this repository and install it with pip:

```bash
pip install .
```

## Usage

### Basic Usage

Initialize the cache at the start of your application:

```python
from flask import Flask
from cachecade import init_cache, cachecaded

app = Flask(__name__)

# Initialize with default settings (tries Replit DB, then Redis, then memory)
init_cache()

@app.route('/data')
@cachecaded(ttl=60)  # Cache results for 60 seconds
def get_data():
    # Your expensive data retrieval operation here
    return {"result": "some data"}
```

### Custom Storage Configuration

Specify the order of storage engines to try:

```python
# Prefer Redis, fall back to memory (skip Replit)
init_cache(storage_engines=['redis', 'memory'])

# Use only in-memory caching
init_cache(storage_engines=['memory'])
```

### Using Cache Prefix

Adding a prefix to your cache keys helps with namespacing and prevents collisions:

```python
# All cache keys will be prefixed with "myapp:"
init_cache(prefix="myapp")

@app.route('/user/<user_id>')
@cachecaded(ttl=300)  # Cache for 5 minutes
def get_user(user_id):
    # The actual cache key will include the "myapp:" prefix
    return {"user_id": user_id, "name": "Example User"}
```

### Using with Flask Blueprints

Cachecade works seamlessly with Flask blueprints:

```python
from flask import Flask, Blueprint
from cachecade import init_cache, cachecaded

app = Flask(__name__)
# Initialize cache with a prefix for this specific app
init_cache(prefix="myservice")

# Create a blueprint for API endpoints
api = Blueprint('api', __name__, url_prefix='/api')

@api.route('/users')
@cachecaded(ttl=120)  # Cache for 2 minutes
def get_users():
    # This function's results will be cached
    return {"users": ["Alice", "Bob", "Charlie"]}

@api.route('/products')
@cachecaded(ttl=300)  # Cache for 5 minutes
def get_products():
    # This function's results will also be cached
    return {"products": ["Product A", "Product B"]}

# Register the blueprint with the app
app.register_blueprint(api)

if __name__ == '__main__':
    app.run(debug=True)
```

### Blueprints in Separate Files

For larger applications, it's common to organize blueprints in separate files or modules. Here's how to use Cachecade in this scenario:

#### Project Structure
```
myapp/
  ├── __init__.py         # Main application factory
  ├── blueprints/
  │   ├── __init__.py
  │   ├── users.py        # Users blueprint
  │   └── products.py     # Products blueprint
  └── app.py              # Application entry point
```

#### Main Application (`myapp/__init__.py`)
```python
from flask import Flask
from cachecade import init_cache

def create_app():
    app = Flask(__name__)
    
    # Initialize cache with a prefix for the entire app
    init_cache(prefix="myapp")
    
    # Register blueprints
    from myapp.blueprints.users import users_bp
    from myapp.blueprints.products import products_bp
    
    app.register_blueprint(users_bp)
    app.register_blueprint(products_bp)
    
    return app
```

#### Users Blueprint (`myapp/blueprints/users.py`)
```python
from flask import Blueprint, jsonify
from cachecade import cachecaded

users_bp = Blueprint('users', __name__, url_prefix='/users')

@users_bp.route('/')
@cachecaded(ttl=300)  # Cache for 5 minutes
def get_users():
    # Expensive database query simulation
    users = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    return jsonify(users)

@users_bp.route('/<int:user_id>')
@cachecaded(ttl=180)  # Cache for 3 minutes
def get_user(user_id):
    # The prefix is applied from the init_cache() call in the main app
    return jsonify({"id": user_id, "name": f"User {user_id}"})
```

#### Products Blueprint (`myapp/blueprints/products.py`)
```python
from flask import Blueprint, jsonify
from cachecade import cachecaded

products_bp = Blueprint('products', __name__, url_prefix='/products')

@products_bp.route('/')
@cachecaded(ttl=600)  # Cache for 10 minutes
def get_products():
    # Expensive database query simulation
    products = [{"id": 1, "name": "Product A"}, {"id": 2, "name": "Product B"}]
    return jsonify(products)
```

#### Application Entry Point (`myapp/app.py`)
```python
from myapp import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
```

In this structure:
1. The cache is initialized once in the application factory
2. The cache prefix is defined globally for the entire application
3. Each blueprint is in its own file, but they all use the same cache instance
4. The `cachecaded` decorator works seamlessly across all blueprints

### Advanced Example with Environment Configuration

```python
import os
from flask import Flask
from cachecade import init_cache, cachecaded

app = Flask(__name__)

# Set up cache based on environment
if os.environ.get('ENVIRONMENT') == 'production':
    # In production, try Redis first, then fall back to memory
    init_cache(storage_engines=['redis', 'memory'], prefix="prod")
else:
    # In development, just use memory caching
    init_cache(storage_engines=['memory'], prefix="dev")

@app.route('/data')
@cachecaded(ttl=60)
def get_data():
    return {"status": "success"}
```

## Note on Redis Configuration

When using Redis as a caching backend, make sure to set the `REDIS_URL` environment variable:

```bash
export REDIS_URL="redis://localhost:6379/0"
```

Or in your application code:

```python
import os
os.environ['REDIS_URL'] = "redis://localhost:6379/0"
```
