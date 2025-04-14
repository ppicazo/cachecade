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
