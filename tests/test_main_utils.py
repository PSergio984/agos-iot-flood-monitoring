import json
from pathlib import Path
from types import SimpleNamespace

import main


def test_safe_ws_url_strips_sensitive_parts():
    url = "wss://user:pass@example.com:9000/ws/path?a=1#frag"
    assert main._safe_ws_url(url) == "wss://example.com:9000"


def test_safe_ws_url_invalid_value():
    assert main._safe_ws_url(None) == "<invalid url>"


def test_send_image_websocket_returns_false_when_ws_lib_unavailable(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"abc")

    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", False)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:8000/ws")

    assert main.send_image_websocket(str(image)) is False


def test_send_image_websocket_returns_false_when_url_missing(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"abc")

    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "")

    assert main.send_image_websocket(str(image)) is False


def test_send_image_websocket_success(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"jpeg-bytes")

    class FakeWS:
        def __init__(self):
            self.frames = []
            self.closed = False
            self.connected = True

        def send(self, payload):
            self.frames.append(("text", payload))

        def send_binary(self, payload):
            self.frames.append(("binary", payload))

        def close(self):
            self.closed = True
            self.connected = False

    fake_ws = FakeWS()

    class FakeWebsocketModule:
        class WebSocketTimeoutException(Exception):
            pass

        class WebSocketConnectionClosedException(Exception):
            pass

        @staticmethod
        def create_connection(_url, timeout):
            assert timeout == 10
            return fake_ws

    monkeypatch.setattr(main, "_websocket", FakeWebsocketModule)
    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:9000/ws")
    monkeypatch.setattr(main, "WS_SEND_METADATA_FIRST", True)

    assert main.send_image_websocket(
        str(image),
        cloudinary_url="https://cdn/x.jpg",
        extra_metadata={"frame_role": "camera_frame", "phase": "day"},
    ) is True
    # Connection stays open persistently
    assert fake_ws.closed is False
    assert len(fake_ws.frames) == 2

    frame_type, text_payload = fake_ws.frames[0]
    assert frame_type == "text"
    metadata = json.loads(text_payload)
    assert metadata["type"] == "image"
    assert metadata["filename"] == Path(image).name
    assert metadata["cloudinary_url"] == "https://cdn/x.jpg"
    assert metadata["frame_role"] == "camera_frame"
    assert metadata["phase"] == "day"

    frame_type, binary_payload = fake_ws.frames[1]
    assert frame_type == "binary"
    assert binary_payload == b"jpeg-bytes"

    # Verify closing the client explicitly closes the underlying socket
    main.get_ws_client().close()
    assert fake_ws.closed is True


def test_send_image_websocket_binary_only_mode(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"jpeg-bytes")

    class FakeWS:
        def __init__(self):
            self.frames = []
            self.closed = False
            self.connected = True

        def send(self, payload):
            self.frames.append(("text", payload))

        def send_binary(self, payload):
            self.frames.append(("binary", payload))

        def close(self):
            self.closed = True
            self.connected = False

    fake_ws = FakeWS()

    class FakeWebsocketModule:
        class WebSocketTimeoutException(Exception):
            pass

        class WebSocketConnectionClosedException(Exception):
            pass

        @staticmethod
        def create_connection(_url, timeout):
            assert timeout == 10
            return fake_ws

    monkeypatch.setattr(main, "_websocket", FakeWebsocketModule)
    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:9000/ws")
    monkeypatch.setattr(main, "WS_SEND_METADATA_FIRST", False)

    assert main.send_image_websocket(str(image), cloudinary_url="https://cdn/x.jpg") is True
    assert fake_ws.closed is False
    assert fake_ws.frames == [("binary", b"jpeg-bytes")]
    main.get_ws_client().close()
    assert fake_ws.closed is True


def test_send_image_websocket_reuses_connection(monkeypatch, tmp_path):
    image1 = tmp_path / "img1.jpg"
    image1.write_bytes(b"frame-1")
    image2 = tmp_path / "img2.jpg"
    image2.write_bytes(b"frame-2")

    class FakeWS:
        def __init__(self):
            self.frames = []
            self.closed = False
            self.connected = True

        def send(self, payload):
            self.frames.append(("text", payload))

        def send_binary(self, payload):
            self.frames.append(("binary", payload))

        def close(self):
            self.closed = True
            self.connected = False

    connect_count = 0
    fake_ws = FakeWS()

    class FakeWebsocketModule:
        class WebSocketTimeoutException(Exception):
            pass

        class WebSocketConnectionClosedException(Exception):
            pass

        @staticmethod
        def create_connection(_url, timeout):
            nonlocal connect_count
            connect_count += 1
            return fake_ws

    monkeypatch.setattr(main, "_websocket", FakeWebsocketModule)
    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:9000/ws")
    monkeypatch.setattr(main, "WS_SEND_METADATA_FIRST", False)

    assert main.send_image_websocket(str(image1)) is True
    assert main.send_image_websocket(str(image2)) is True
    # create_connection should be called once, reusing persistent connection
    assert connect_count == 1
    assert len(fake_ws.frames) == 2
    main.get_ws_client().close()


def test_send_image_websocket_timeout_path(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"jpeg-bytes")

    class FakeWebsocketModule:
        class WebSocketTimeoutException(Exception):
            pass

        class WebSocketConnectionClosedException(Exception):
            pass

        @staticmethod
        def create_connection(_url, timeout):
            raise FakeWebsocketModule.WebSocketTimeoutException("timeout")

    monkeypatch.setattr(main, "_websocket", FakeWebsocketModule)
    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:9000/ws")

    assert main.send_image_websocket(str(image)) is False


def test_send_image_websocket_closed_connection_path(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"jpeg-bytes")

    class FakeWebsocketModule:
        class WebSocketTimeoutException(Exception):
            pass

        class WebSocketConnectionClosedException(Exception):
            pass

        @staticmethod
        def create_connection(_url, timeout):
            raise FakeWebsocketModule.WebSocketConnectionClosedException("closed")

    monkeypatch.setattr(main, "_websocket", FakeWebsocketModule)
    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:9000/ws")

    assert main.send_image_websocket(str(image)) is False


def test_send_image_websocket_oserror_path(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"jpeg-bytes")

    fake_module = SimpleNamespace(
        WebSocketTimeoutException=RuntimeError,
        WebSocketConnectionClosedException=RuntimeError,
    )

    def _raise(_url, timeout):
        raise OSError("network down")

    fake_module.create_connection = _raise

    monkeypatch.setattr(main, "_websocket", fake_module)
    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:9000/ws")

    assert main.send_image_websocket(str(image)) is False


def test_send_image_websocket_reconnects_after_send_error(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"jpeg-bytes")

    class FakeWS:
        def __init__(self, should_fail=False):
            self.should_fail = should_fail
            self.frames = []
            self.closed = False
            self.connected = True

        def send(self, payload):
            if self.should_fail:
                raise OSError("broken pipe")
            self.frames.append(("text", payload))

        def send_binary(self, payload):
            if self.should_fail:
                raise OSError("broken pipe")
            self.frames.append(("binary", payload))

        def close(self):
            self.closed = True
            self.connected = False

    socket_instances = [FakeWS(should_fail=True), FakeWS(should_fail=False)]

    class FakeWebsocketModule:
        class WebSocketTimeoutException(Exception):
            pass

        class WebSocketConnectionClosedException(Exception):
            pass

        @staticmethod
        def create_connection(_url, timeout):
            return socket_instances.pop(0)

    monkeypatch.setattr(main, "_websocket", FakeWebsocketModule)
    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:9000/ws")
    monkeypatch.setattr(main, "WS_SEND_METADATA_FIRST", False)

    # First send fails due to broken pipe -> resets socket
    assert main.send_image_websocket(str(image)) is False

    # Second send auto-reconnects with new socket and succeeds
    assert main.send_image_websocket(str(image)) is True
    main.get_ws_client().close()

