import json
from pathlib import Path
from types import SimpleNamespace

import main


class FakeWS:
    def __init__(self, should_fail=False):
        self.frames = []
        self.closed = False
        self.connected = True
        self.should_fail = should_fail

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


class FakeWebsocketModule:
    class WebSocketTimeoutException(Exception):
        pass

    class WebSocketConnectionClosedException(Exception):
        pass

    def __init__(self, fake_ws=None, create_fn=None):
        self.fake_ws = fake_ws or FakeWS()
        self.create_fn = create_fn

    def create_connection(self, _url, timeout, **kwargs):
        if self.create_fn:
            try:
                return self.create_fn(_url, timeout, **kwargs)
            except TypeError:
                return self.create_fn(_url, timeout)
        assert timeout == 10
        return self.fake_ws


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

    fake_ws = FakeWS()
    fake_module = FakeWebsocketModule(fake_ws)

    monkeypatch.setattr(main, "_websocket", fake_module)
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

    fake_ws = FakeWS()
    fake_module = FakeWebsocketModule(fake_ws)

    monkeypatch.setattr(main, "_websocket", fake_module)
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

    connect_count = 0
    fake_ws = FakeWS()

    def _create(_url, timeout, **kwargs):
        nonlocal connect_count
        connect_count += 1
        return fake_ws

    fake_module = FakeWebsocketModule(fake_ws, create_fn=_create)

    monkeypatch.setattr(main, "_websocket", fake_module)
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

    def _timeout(_url, _timeout, **kwargs):
        raise FakeWebsocketModule.WebSocketTimeoutException("timeout")

    fake_module = FakeWebsocketModule(create_fn=_timeout)

    monkeypatch.setattr(main, "_websocket", fake_module)
    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:9000/ws")

    assert main.send_image_websocket(str(image)) is False


def test_send_image_websocket_closed_connection_path(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"jpeg-bytes")

    def _closed(_url, _timeout, **kwargs):
        raise FakeWebsocketModule.WebSocketConnectionClosedException("closed")

    fake_module = FakeWebsocketModule(create_fn=_closed)

    monkeypatch.setattr(main, "_websocket", fake_module)
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

    def _raise(_url, timeout, **kwargs):
        raise OSError("network down")

    fake_module.create_connection = _raise

    monkeypatch.setattr(main, "_websocket", fake_module)
    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:9000/ws")

    assert main.send_image_websocket(str(image)) is False


def test_send_image_websocket_reconnects_immediately_after_send_error(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"jpeg-bytes")

    socket_instances = [FakeWS(should_fail=True), FakeWS(should_fail=False)]

    def _create(_url, timeout, **kwargs):
        return socket_instances.pop(0)

    fake_module = FakeWebsocketModule(create_fn=_create)

    monkeypatch.setattr(main, "_websocket", fake_module)
    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:9000/ws")
    monkeypatch.setattr(main, "WS_SEND_METADATA_FIRST", False)

    # First send encounters broken pipe on 1st socket, reconnects immediately to 2nd socket, and succeeds
    assert main.send_image_websocket(str(image)) is True
    main.get_ws_client().close()


def test_send_image_websocket_fails_if_reconnect_also_fails(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"jpeg-bytes")

    socket_instances = [FakeWS(should_fail=True), FakeWS(should_fail=True)]

    def _create(_url, timeout, **kwargs):
        return socket_instances.pop(0)

    fake_module = FakeWebsocketModule(create_fn=_create)

    monkeypatch.setattr(main, "_websocket", fake_module)
    monkeypatch.setattr(main, "WEBSOCKET_AVAILABLE", True)
    monkeypatch.setattr(main, "WEBSOCKET_SERVER_URL", "ws://localhost:9000/ws")
    monkeypatch.setattr(main, "WS_SEND_METADATA_FIRST", False)

    # Both initial and retry fail -> returns False
    assert main.send_image_websocket(str(image)) is False
    main.get_ws_client().close()


def test_persistent_websocket_client_custom_parameters(tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"custom-bytes")

    fake_ws = FakeWS()
    fake_module = FakeWebsocketModule(fake_ws)

    client = main.PersistentWebSocketClient(
        url="ws://localhost:9999/ws",
        sensor_device_id=42,
        send_metadata_first=True,
        ws_module=fake_module,
    )

    assert client.send(str(image)) is True
    assert len(fake_ws.frames) == 2
    metadata = json.loads(fake_ws.frames[0][1])
    assert metadata["sensor_device_id"] == 42
    client.close()


def test_persistent_websocket_client_concurrent_sends(tmp_path):
    import threading

    fake_ws = FakeWS()
    fake_module = FakeWebsocketModule(fake_ws)

    client = main.PersistentWebSocketClient(
        url="ws://localhost:9999/ws",
        sensor_device_id=1,
        send_metadata_first=True,
        ws_module=fake_module,
    )

    threads = []
    results = []

    def _worker(idx):
        img_path = tmp_path / f"img_{idx}.jpg"
        img_path.write_bytes(f"content-{idx}".encode())
        res = client.send(str(img_path))
        results.append(res)

    for i in range(10):
        t = threading.Thread(target=_worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert all(results)
    assert len(results) == 10
    assert len(fake_ws.frames) == 20
    client.close()


def test_persistent_websocket_client_proactive_age_refresh(monkeypatch, tmp_path):
    image = tmp_path / "img.jpg"
    image.write_bytes(b"content")

    created_sockets = []

    def _create(_url, timeout, **kwargs):
        ws = FakeWS()
        created_sockets.append(ws)
        return ws

    fake_module = FakeWebsocketModule(create_fn=_create)

    client = main.PersistentWebSocketClient(
        url="ws://localhost:9999/ws",
        max_connection_age_s=10.0,
        ws_module=fake_module,
    )

    current_time = 1000.0
    monkeypatch.setattr(main.time, "monotonic", lambda: current_time)

    # 1st send: creates socket 1
    assert client.send(str(image)) is True
    assert len(created_sockets) == 1

    # 2nd send at +5s (age 5s < 10s): reuses socket 1
    current_time = 1005.0
    assert client.send(str(image)) is True
    assert len(created_sockets) == 1

    # 3rd send at +11s (age 11s >= 10s): proactively recycles socket 1 and creates socket 2
    current_time = 1011.0
    assert client.send(str(image)) is True
    assert len(created_sockets) == 2
    assert created_sockets[0].closed is True
    assert created_sockets[1].closed is False
    client.close()


def test_config_get_env_var(monkeypatch):
    import config

    monkeypatch.setenv("TEST_STR", "  hello  ")
    assert config.get_env_var("TEST_STR", "default") == "hello"

    monkeypatch.setenv("TEST_EMPTY", "   ")
    assert config.get_env_var("TEST_EMPTY", "default") == "default"

    monkeypatch.setenv("TEST_INT", "42")
    assert config.get_env_var("TEST_INT", "10", int) == 42

    monkeypatch.setenv("TEST_FLOAT", "3.14")
    assert config.get_env_var("TEST_FLOAT", "1.0", float) == 3.14

    monkeypatch.setenv("TEST_BOOL_TRUE", "yes")
    assert config.get_env_var("TEST_BOOL_TRUE", "false", bool) is True

    monkeypatch.setenv("TEST_BOOL_FALSE", "0")
    assert config.get_env_var("TEST_BOOL_FALSE", "true", bool) is False

    # Test alias list priority
    monkeypatch.delenv("TEST_ALIAS_PRIMARY", raising=False)
    monkeypatch.setenv("TEST_ALIAS_SECONDARY", "found_secondary")
    assert config.get_env_var(["TEST_ALIAS_PRIMARY", "TEST_ALIAS_SECONDARY"], "fallback") == "found_secondary"

    # Test invalid cast fallback
    monkeypatch.setenv("TEST_BAD_NUM", "not_a_number")
    assert config.get_env_var("TEST_BAD_NUM", "99", int) == 99


def test_evaluate_and_gate_frame(monkeypatch, tmp_path):
    img = tmp_path / "frame.jpg"
    img.write_bytes(b"data")

    # Case 1: Normal usable frame
    monkeypatch.setattr(main, "get_frame_quality_metrics", lambda p: {"brightness": 100.0, "contrast_stddev": 40.0, "laplacian_var": 200.0})
    monkeypatch.setattr(main, "is_frame_dark", lambda m: False)
    monkeypatch.setattr(main, "is_frame_obscured", lambda m: False)
    monkeypatch.setattr(main, "is_frame_usable", lambda p: True)

    night_vision_triggered = False
    monkeypatch.setattr(main, "force_night_vision", lambda: nonlocal_trigger())
    def nonlocal_trigger():
        nonlocal night_vision_triggered
        night_vision_triggered = True

    assert main._evaluate_and_gate_frame(str(img), context_label="test") is True
    assert night_vision_triggered is False

    # Case 2: Dark frame triggers night vision and passes gate if usable
    monkeypatch.setattr(main, "is_frame_dark", lambda m: True)
    assert main._evaluate_and_gate_frame(str(img)) is True
    assert night_vision_triggered is True

    # Case 3: Unusable frame is dropped
    monkeypatch.setattr(main, "is_frame_usable", lambda p: False)
    assert main._evaluate_and_gate_frame(str(img), context_label="test") is False




