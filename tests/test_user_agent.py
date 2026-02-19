"""Verify b2ai-comfyui user agent appears in actual HTTP requests."""

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from comfyui_cloud_storage.providers import create_s3_client


class CaptureHandler(BaseHTTPRequestHandler):
    """Captures the User-Agent header from incoming requests."""
    captured_user_agent = None

    def do_GET(self, *args, **kwargs):
        CaptureHandler.captured_user_agent = self.headers.get("User-Agent", "")
        # Return a minimal valid S3 ListBuckets XML response
        body = b'<?xml version="1.0"?><ListAllMyBucketsResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Buckets></Buckets></ListAllMyBucketsResult>'
        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # silence request logs


def test_user_agent_in_http_request():
    """Start a local HTTP server, make a real boto3 call, check the User-Agent header."""
    server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    try:
        client = create_s3_client(
            provider="Custom",
            access_key="test",
            secret_key="test",
            endpoint_url=f"http://127.0.0.1:{port}",
            region="us-east-1",
        )
        client.list_buckets()
    except Exception:
        pass  # response parsing may fail, that's fine - we just need the header
    finally:
        thread.join(timeout=5)
        server.server_close()

    assert CaptureHandler.captured_user_agent is not None, "No request received"
    assert "b2ai-comfyui" in CaptureHandler.captured_user_agent, (
        f"Expected 'b2ai-comfyui' in User-Agent, got: {CaptureHandler.captured_user_agent}"
    )
