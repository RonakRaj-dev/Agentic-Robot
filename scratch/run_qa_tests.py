import sys
import os
from pathlib import Path

# Add project root and storage_service to python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORAGE_SERVICE_DIR = PROJECT_ROOT / "storage_service"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if str(STORAGE_SERVICE_DIR) not in sys.path:
    sys.path.append(str(STORAGE_SERVICE_DIR))


try:
    import services
    print("DEBUG Top level services path:", getattr(services, "__file__", "None"))
except Exception as e:
    print("DEBUG Top level services import failed:", e)

import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch


class SiliconProjectQATests(unittest.TestCase):
    """
    QA Test Suite verifying Category 1, 2, and 3 production issues
    as a strict senior software tester.
    """

    def test_category_1_pubsub_multiple_subscribers_bug(self):
        """
        Verify that RedisPubSubManager fails to subscribe subsequent channels
        on Redis if self.pubsub is already initialized (Critical Category 1).
        """
        print("\n[TEST] Verifying Category 1: Multi-Client WebSocket Silence")
        from services.redis_pubsub import RedisPubSubManager
        
        # Instantiate a test PubSub manager
        manager = RedisPubSubManager(redis_url="redis://localhost:6379/0")
        manager.is_connected = True
        
        # Mock redis client and its pubsub object
        mock_redis = MagicMock()
        mock_pubsub = MagicMock()
        
        # Setup async return values
        mock_pubsub.subscribe = AsyncMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        manager.redis_client = mock_redis
        
        # Step 1: Subscribe to Channel A
        print("  -> Subscribing first client to 'channel_A'...")
        asyncio.run(manager.subscribe("channel_A", lambda ch, msg: None))
        
        self.assertIsNotNone(manager.pubsub)
        self.assertEqual(len(manager._listeners["channel_A"]), 1)
        mock_pubsub.subscribe.assert_called_with("channel_A")
        print("  -> First client subscribed successfully on Redis.")

        # Reset mock call history
        mock_pubsub.subscribe.reset_mock()
        mock_redis.pubsub.reset_mock()

        # Step 2: Subscribe to Channel B
        print("  -> Subscribing second client to 'channel_B'...")
        asyncio.run(manager.subscribe("channel_B", lambda ch, msg: None))
        
        self.assertEqual(len(manager._listeners["channel_B"]), 1)
        
        # Check if code skipped subscribing 'channel_B' on Redis connection
        # because not self.pubsub is False!
        print(f"  -> Was redis_client.pubsub() called? {mock_redis.pubsub.called}")
        print(f"  -> Was pubsub.subscribe('channel_B') called? {mock_pubsub.subscribe.called}")
        
        # Verify the BUG exists!
        self.assertFalse(mock_pubsub.subscribe.called, 
                         "BUG FOUND: Subscribing to a second channel did not trigger Redis subscribe!")
        print("  [RESULT] CRITICAL BUG CONFIRMED: Subsequent WebSocket clients are SILENT because they never subscribe on Redis!")

    def test_category_2_cors_configuration_crash(self):
        """
        Verify that CORS allows wildcard origins with allow_credentials=True,
        which triggers crashes in Starlette/FastAPI (Category 2, Bug 3).
        """
        print("\n[TEST] Verifying Category 2: Starlette CORS Configuration Crash")
        from api.main import app
        
        # Look for CORSMiddleware in fastapi app middleware stack
        cors_middleware = None
        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware.cls):
                cors_middleware = middleware
                break
                
        self.assertIsNotNone(cors_middleware, "CORSMiddleware should be registered in FastAPI app")
        
        # Get configured parameters from kwargs
        kwargs = cors_middleware.kwargs
        allow_origins = kwargs.get("allow_origins", [])
        allow_credentials = kwargs.get("allow_credentials", False)
        
        print(f"  -> Configured allow_origins: {allow_origins}")
        print(f"  -> Configured allow_credentials: {allow_credentials}")
        
        # Assert combination violation
        is_wildcard = "*" in allow_origins
        if is_wildcard and allow_credentials:
            print("  [RESULT] SECURITY & COMPATIBILITY VIOLATION CONFIRMED:")
            print("           FastAPI/Starlette CORSMiddleware cannot allow wildcard '*' origins when allow_credentials=True.")
            self.assertTrue(True)
        else:
            self.fail("CORS is configured securely (wildcard not combined with credentials)")

    def test_category_2_path_traversal_api_vulnerability(self):
        """
        Verify that /ingest endpoint is vulnerable to Path Traversal (Category 2, Bug 2).
        """
        print("\n[TEST] Verifying Category 2: Path Traversal Vulnerability")
        from api.routes_ingest import router
        
        # Let's inspect the route logic for /ingest
        # Path traversal occurs when joining directories directly with file.filename:
        # file_path = os.path.join(save_dir, file.filename)
        
        import inspect
        source = inspect.getsource(router.routes[0].endpoint)
        
        self.assertIn("file.filename", source)
        self.assertIn("os.path.join", source)
        
        # Verify lack of security sanitization on paths (like os.path.basename)
        self.assertNotIn("os.path.basename(file.filename)", source)
        print("  [RESULT] SECURITY VULNERABILITY CONFIRMED:")
        print("           api/routes_ingest.py directly uses raw filename from client inside os.path.join(), allowing Path Traversal!")

    def test_category_2_synchronous_db_queries_blocking_loop(self):
        """
        Verify that SessionStateManager uses synchronous MongoClient which blocks the event loop (Category 2, Bug 4).
        """
        print("\n[TEST] Verifying Category 2: Synchronous DB Queries Blocking Async Loop")
        from state.sessionState import SessionStateManager
        import inspect
        
        # SessionStateManager must use pymongo.MongoClient which makes blocking network calls
        source = inspect.getsource(SessionStateManager.__init__)
        self.assertIn("MongoClient", source)
        print("  [RESULT] ARCHITECTURAL BOTTLENECK CONFIRMED:")
        print("           SessionStateManager connects via synchronous pymongo.MongoClient, blocking async coroutines in endpoints.")

    def test_category_3_dead_cache_implementation(self):
        """
        Verify that TTLCache only writes locally and never utilizes Redis client (Category 3, Bug 5).
        """
        print("\n[TEST] Verifying Category 3: Dead Cache Implementation (Redis Bypass)")
        from services.cache_service import TTLCache
        
        cache = TTLCache()
        cache.redis_client = MagicMock()
        cache.is_connected = True
        
        # Write to cache
        cache.set("qa_test_key", "val_123")
        
        # Check if local dict was populated
        self.assertIn("qa_test_key", cache._store)
        
        # Check if Redis was written to
        print(f"  -> Was Redis client set/setex called? {cache.redis_client.set.called or cache.redis_client.setex.called}")
        self.assertFalse(cache.redis_client.set.called)
        self.assertFalse(cache.redis_client.setex.called)
        print("  [RESULT] CACHE DEFECT CONFIRMED: cache_service connects to Redis but only gets/sets locally in RAM dictionary.")

    def test_category_3_pymupdf_double_parsing(self):
        """
        Verify that PyMuPDFService calls to_markdown twice, wasting CPU (Category 3, Bug 7).
        """
        print("\n[TEST] Verifying Category 3: Inefficient Double-Parsing of PDFs")
        from storage_service.services.pymupdf.pymupdf_service import PyMuPDFService
        import inspect
        
        source = inspect.getsource(PyMuPDFService.extract_markdown)
        
        # Count occurrences of to_markdown
        count = source.count("to_markdown")
        print(f"  -> Number of times to_markdown is called in extract_markdown: {count}")
        self.assertEqual(count, 2, "to_markdown should be called twice in extract_markdown causing CPU waste")
        print("  [RESULT] PERFORMANCE DEFECT CONFIRMED: PyMuPDFService processes convert-to-markdown twice per PDF.")

if __name__ == "__main__":
    unittest.main()
