import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import json
import time
import sys
from importlib import reload
from cachecade import generate_cache_key, init_cache, get_cache_entry, set_cache_entry
import cachecade.caching

class TestCaching(unittest.TestCase):
    def setUp(self):
        # Reset cache settings before each test
        reload(cachecade.caching)
        cachecade.caching.init_cache(storage_engines=['memory'], prefix=None)
        
    def test_generate_cache_key_basic(self):
        """Test basic cache key generation"""
        key = generate_cache_key('test_func', (1, 2), {'a': 3})
        self.assertIsInstance(key, str)
        self.assertGreater(len(key), 0)
        
    def test_cache_prefix(self):
        """Test cache key generation with different prefixes in init_cache"""
        # Without prefix
        init_cache(storage_engines=['memory'], prefix=None)
        key1 = generate_cache_key('test_func', (1, 2), {'a': 3})
        
        # With prefix 'app1'
        init_cache(storage_engines=['memory'], prefix='app1')
        key2 = generate_cache_key('test_func', (1, 2), {'a': 3})
        
        # Keys should be different with different prefixes
        self.assertNotEqual(key1, key2)
        
        # Same prefix should produce the same key
        key3 = generate_cache_key('test_func', (1, 2), {'a': 3})
        self.assertEqual(key2, key3)
        
        # Different prefix
        init_cache(storage_engines=['memory'], prefix='app2')
        key4 = generate_cache_key('test_func', (1, 2), {'a': 3})
        self.assertNotEqual(key2, key4)
    
    def test_generate_cache_key_consistency(self):
        """Test that the same inputs always produce the same key"""
        key1 = generate_cache_key('test_func', (1, 2), {'a': 3})
        key2 = generate_cache_key('test_func', (1, 2), {'a': 3})
        self.assertEqual(key1, key2)
    
    def test_generate_cache_key_different_args(self):
        """Test that different arguments produce different keys"""
        key1 = generate_cache_key('test_func', (1, 2), {'a': 3})
        key2 = generate_cache_key('test_func', (1, 3), {'a': 3})  # changed arg
        key3 = generate_cache_key('test_func', (1, 2), {'a': 4})  # changed kwarg
        key4 = generate_cache_key('other_func', (1, 2), {'a': 3})  # changed function name
        
        self.assertNotEqual(key1, key2)
        self.assertNotEqual(key1, key3)
        self.assertNotEqual(key1, key4)
        self.assertNotEqual(key2, key3)
        self.assertNotEqual(key2, key4)
        self.assertNotEqual(key3, key4)
    
    def test_generate_cache_key_complex_types(self):
        """Test cache key generation with complex argument types"""
        # Test with nested structures
        key1 = generate_cache_key('test_func', ([1, 2], {'b': 3}), {'c': [4, 5]})
        self.assertIsInstance(key1, str)
        
        # Test with different object types
        key2 = generate_cache_key('test_func', (None, True, 1.23), {'d': b'bytes'})
        self.assertIsInstance(key2, str)
        
        self.assertNotEqual(key1, key2)

    # New tests for different storage backends
    def test_redis_backend(self):
        """Test Redis storage backend with mocks"""
        # Create mock Redis module
        mock_redis = MagicMock()
        mock_redis_client = MagicMock()
        mock_redis.from_url.return_value = mock_redis_client

        # Setup responses for cache miss and hit
        mock_response = json.dumps((time.time(), {'data': 'test_value'})).encode('utf-8')
        mock_redis_client.get.side_effect = [None, mock_response]
        
        # Patch the import system to mock Redis
        with patch.dict('sys.modules', {'redis': mock_redis}):
            with patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'}):
                # Re-initialize the cache module to use our mocked Redis
                reload(cachecade.caching)
                cachecade.caching.init_cache(storage_engines=['redis'])
                
                # Verify Redis backend was selected
                self.assertEqual(cachecade.caching.cache_backend, 'redis')
                
                # Test cache operations
                test_key = generate_cache_key('test_func', (), {})
                
                # Test cache miss
                self.assertIsNone(get_cache_entry(test_key))
                
                # Test setting cache entry
                test_value = json.dumps((time.time(), {'data': 'test_value'}))
                set_cache_entry(test_key, test_value, ttl=60)
                mock_redis_client.setex.assert_called_once()
                
                # Test cache hit (mock returns the encoded response on second call)
                cached_data = get_cache_entry(test_key)
                self.assertIsNotNone(cached_data)

    def test_replit_backend(self):
        """Test Replit storage backend with mocks"""
        # Create mock for replit.db
        mock_db = {}
        mock_replit_db = MagicMock()
        
        # Configure the mock for dictionary-like behavior
        def mock_get(key):
            return mock_db.get(key)
        
        # Fix: Correctly implement __setitem__ as a method that accepts self, key, value
        def mock_setitem(self, key, value):
            mock_db[key] = value
        
        mock_replit_db.get.side_effect = mock_get
        mock_replit_db.__setitem__ = mock_setitem
        
        # Create mock for replit module
        mock_replit = MagicMock()
        mock_replit.db = mock_replit_db
        
        # Patch the import system
        with patch.dict('sys.modules', {'replit': mock_replit}):
            # Re-initialize the cache module to use our mocked Replit DB
            reload(cachecade.caching)
            cachecade.caching.replit_db = mock_replit_db
            cachecade.caching.init_cache(storage_engines=['replit'])
            
            # Verify Replit backend was selected
            self.assertEqual(cachecade.caching.cache_backend, 'replit')
            
            # Test cache operations
            test_key = generate_cache_key('test_func', (), {})
            test_value = json.dumps((time.time(), {'data': 'test_value'}))
            
            # Test cache miss
            self.assertIsNone(get_cache_entry(test_key))
            
            # Test setting cache entry
            set_cache_entry(test_key, test_value)
            self.assertEqual(mock_db.get(test_key), test_value)
            
            # Test cache hit
            cached_data = get_cache_entry(test_key)
            self.assertEqual(cached_data, test_value)

    def test_memory_backend(self):
        """Test in-memory storage backend"""
        # Initialize with memory backend
        reload(cachecade.caching)
        cachecade.caching.init_cache(storage_engines=['memory'])
        
        # Verify memory backend was selected
        self.assertEqual(cachecade.caching.cache_backend, 'memory')
        
        # Test cache operations
        test_key = generate_cache_key('test_func', (), {})
        test_value = json.dumps((time.time(), {'data': 'test_value'}))
        
        # Test cache miss
        self.assertIsNone(get_cache_entry(test_key))
        self.assertNotIn(test_key, cachecade.caching.memory_store)
        
        # Test setting cache entry
        set_cache_entry(test_key, test_value)
        self.assertIn(test_key, cachecade.caching.memory_store)
        self.assertEqual(cachecade.caching.memory_store[test_key], test_value)
        
        # Test cache hit
        cached_data = get_cache_entry(test_key)
        self.assertEqual(cached_data, test_value)
        
    def test_init_cache_priority(self):
        """Test the priority of storage engines in init_cache"""
        # First, set up mocks for Redis
        mock_redis = MagicMock()
        mock_redis_client = MagicMock()
        mock_redis.from_url.return_value = mock_redis_client
        
        # Next, set up mocks for Replit
        mock_replit_db = MagicMock()
        mock_replit = MagicMock()
        mock_replit.db = mock_replit_db
        
        # Now test different priority scenarios
        with patch.dict('sys.modules', {'redis': mock_redis, 'replit': mock_replit}):
            with patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'}):
                # Test priority: Replit > Redis > Memory
                reload(cachecade.caching)
                cachecade.caching.replit_db = mock_replit_db
                cachecade.caching.init_cache(storage_engines=['replit', 'redis', 'memory'])
                self.assertEqual(cachecade.caching.cache_backend, 'replit')
                
                # Test priority: Redis > Replit > Memory
                reload(cachecade.caching)
                cachecade.caching.replit_db = mock_replit_db
                cachecade.caching.init_cache(storage_engines=['redis', 'replit', 'memory'])
                self.assertEqual(cachecade.caching.cache_backend, 'redis')
                
                # Test priority: Memory > Redis > Replit
                reload(cachecade.caching)
                cachecade.caching.replit_db = mock_replit_db
                cachecade.caching.init_cache(storage_engines=['memory', 'redis', 'replit'])
                self.assertEqual(cachecade.caching.cache_backend, 'memory')
                
                # Test fallback when Redis import fails
                with patch.dict('sys.modules', {'redis': None, 'replit': mock_replit}):
                    reload(cachecade.caching)
                    cachecade.caching.replit_db = mock_replit_db
                    cachecade.caching.init_cache(storage_engines=['redis', 'replit', 'memory'])
                    self.assertEqual(cachecade.caching.cache_backend, 'replit')
                
                # Test fallback when both Redis and Replit are unavailable
                with patch.dict('sys.modules', {'redis': None}):
                    reload(cachecade.caching)
                    cachecade.caching.replit_db = None
                    cachecade.caching.init_cache(storage_engines=['redis', 'replit', 'memory'])
                    self.assertEqual(cachecade.caching.cache_backend, 'memory')

    def test_replit_cached_decorator(self):
        """Test the replit_cached decorator functionality"""
        from cachecade import replit_cached
        from flask import jsonify
        
        # Create a test function using the decorator
        @replit_cached(ttl=10)
        def test_function(a, b, c=None):
            return {'result': a + b, 'c': c}
        
        # Mock Flask's jsonify function
        original_jsonify = cachecade.caching.jsonify
        mock_jsonify = MagicMock()
        mock_jsonify.side_effect = lambda x: x  # Just return the input
        cachecade.caching.jsonify = mock_jsonify
        
        try:
            # Test first call (cache miss)
            result1 = test_function(5, 10, c='test')
            self.assertEqual(result1['result'], 15)
            self.assertEqual(result1['c'], 'test')
            
            # Test second call with same args (should be cache hit)
            result2 = test_function(5, 10, c='test')
            self.assertEqual(result2['result'], 15)
            self.assertEqual(result2['c'], 'test')
            
            # Test call with different args (should be cache miss)
            result3 = test_function(7, 3, c='other')
            self.assertEqual(result3['result'], 10)
            self.assertEqual(result3['c'], 'other')
            
        finally:
            # Restore original jsonify
            cachecade.caching.jsonify = original_jsonify

    def test_cache_expiration_in_memory(self):
        """Test that cached entries expire after their TTL period in memory"""
        from cachecade import replit_cached
        from flask import jsonify
        
        # Set a very short TTL for testing (1 second)
        SHORT_TTL = 1
        
        # Create a test function using the decorator with short TTL
        @replit_cached(ttl=SHORT_TTL)
        def test_function(a, b):
            # This counter helps us verify the function was called again after expiration
            test_function.calls += 1
            return {'result': a + b, 'calls': test_function.calls}
        
        # Initialize call counter
        test_function.calls = 0
        
        # Mock Flask's jsonify function
        original_jsonify = cachecade.caching.jsonify
        mock_jsonify = MagicMock()
        mock_jsonify.side_effect = lambda x: x  # Just return the input
        cachecade.caching.jsonify = mock_jsonify
        
        try:
            # First call should execute the function (cache miss)
            result1 = test_function(5, 10)
            self.assertEqual(result1['result'], 15)
            self.assertEqual(result1['calls'], 1)
            
            # Second immediate call should use cached result (cache hit)
            result2 = test_function(5, 10)
            self.assertEqual(result2['result'], 15)
            # Call count should still be 1 because we used cached result
            self.assertEqual(result2['calls'], 1)
            
            print("Waiting for cache to expire...")
            # Wait for the cache to expire (slightly longer than TTL)
            time.sleep(SHORT_TTL + 0.5)
            
            # Call again after TTL expired, should execute the function again
            result3 = test_function(5, 10)
            self.assertEqual(result3['result'], 15)
            # Call count should be 2 because cache expired and function ran again
            self.assertEqual(result3['calls'], 2)
            
        finally:
            # Restore original jsonify
            cachecade.caching.jsonify = original_jsonify

if __name__ == '__main__':
    unittest.main()
