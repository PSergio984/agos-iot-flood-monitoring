import burst_capture

def test_ensure_dir(tmp_path):
    d = tmp_path / 'new_folder'
    burst_capture._ensure_dir(str(d))
    assert d.exists()

def test_upload_to_cloudinary_success(monkeypatch):
    def fake_upload(filepath, folder, tags, context):
        assert filepath == 'test.jpg'
        assert folder == 'agos/training_test'
        assert 'test' in tags
        return {'secure_url': 'https://cdn.example.com/test.jpg'}

    monkeypatch.setattr(burst_capture.cloudinary.uploader, 'upload', fake_upload)
    result = burst_capture.upload_to_cloudinary('test.jpg', '123', label='test')
    assert isinstance(result, burst_capture.UploadResult)
    assert result.success is True
    assert result.filepath == 'test.jpg'
    assert result.detail == 'https://cdn.example.com/test.jpg'
    # Test backwards-compatible tuple unpacking
    ok, fp, url = result
    assert ok is True and fp == 'test.jpg' and url == 'https://cdn.example.com/test.jpg'


def test_upload_to_cloudinary_failure(monkeypatch):
    def fake_upload(filepath, folder, tags, context):
        raise RuntimeError('upload error')

    monkeypatch.setattr(burst_capture.cloudinary.uploader, 'upload', fake_upload)
    result = burst_capture.upload_to_cloudinary('test.jpg', '123', label='test')
    assert result.success is False
    assert result.filepath == 'test.jpg'
    assert 'upload error' in result.detail

def test_upload_all_concurrent(monkeypatch, tmp_path):
    files = [str(tmp_path / f'img_{i}.jpg') for i in range(5)]
    for f in files:
        with open(f, 'w') as fh:
            fh.write('x')

    def fake_upload(filepath, session_id_or_context, label="raining", cloud_folder=None):
        return burst_capture.UploadResult(True, filepath, 'https://cdn/ok.jpg')

    monkeypatch.setattr(burst_capture, 'upload_to_cloudinary', fake_upload)
    results = burst_capture.upload_all_concurrent(files, 'session1', label='raining', max_workers=2)
    assert len(results) == 5
    assert all(ok for ok, _, _ in results)

    # Test with BurstUploadContext instance
    ctx = burst_capture.BurstUploadContext(session_id='session2', label='custom', cloud_folder='agos/test')
    results_ctx = burst_capture.upload_all_concurrent(files, ctx, max_workers=2)
    assert len(results_ctx) == 5
    assert all(res.success for res in results_ctx)


def test_upload_to_cloudinary_with_context(monkeypatch):
    def fake_upload(filepath, folder, tags, context):
        assert filepath == 'test.jpg'
        assert folder == 'custom/folder'
        assert 'custom_label' in tags
        return {'secure_url': 'https://cdn.example.com/test_ctx.jpg'}

    monkeypatch.setattr(burst_capture.cloudinary.uploader, 'upload', fake_upload)
    ctx = burst_capture.BurstUploadContext(session_id='999', label='custom_label', cloud_folder='custom/folder')
    result = burst_capture.upload_to_cloudinary('test.jpg', ctx)
    assert result.success is True
    assert result.detail == 'https://cdn.example.com/test_ctx.jpg'


def test_run_countdown(monkeypatch):
    sleeps = []
    monkeypatch.setattr(burst_capture.time, 'sleep', lambda s: sleeps.append(s))
    burst_capture.run_countdown(3)
    assert len(sleeps) == 3


def test_upload_all_concurrent_with_kwargs(monkeypatch, tmp_path):
    files = [str(tmp_path / 'img.jpg')]
    for f in files:
        with open(f, 'w') as fh:
            fh.write('x')

    calls = []

    def fake_upload(filepath, session_id, label="raining", cloud_folder=None):
        calls.append((filepath, session_id, label, cloud_folder))
        return burst_capture.UploadResult(True, filepath, 'https://cdn/ok.jpg')

    monkeypatch.setattr(burst_capture, 'upload_to_cloudinary', fake_upload)

    # Call using exact keyword arguments as in burst_capture.main
    results = burst_capture.upload_all_concurrent(
        files,
        session_id="session_kw",
        label="test_label",
        cloud_folder="agos/test_folder",
        max_workers=1,
    )
    assert len(results) == 1
    assert len(calls) == 1
    # Check that context inside worker was properly populated
    assert calls[0][0] == files[0]
    ctx = calls[0][1]
    assert isinstance(ctx, burst_capture.BurstUploadContext)
    assert ctx.session_id == "session_kw"
    assert ctx.label == "test_label"
    assert ctx.cloud_folder == "agos/test_folder"


def test_burst_capture_main_cli_flow(monkeypatch, tmp_path):
    out_dir = tmp_path / "test_out"

    class FakeCam:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def capture(self, filepath):
            with open(filepath, 'w') as f:
                f.write('frame')
            return filepath

    uploaded = []
    def fake_upload_all(filepaths, session_id, label="raining", cloud_folder=None, max_workers=4):
        uploaded.extend(filepaths)
        return [burst_capture.UploadResult(True, fp, 'https://cdn/ok.jpg') for fp in filepaths]

    monkeypatch.setattr(burst_capture, 'PersistentCamera', FakeCam)
    monkeypatch.setattr(burst_capture, 'upload_all_concurrent', fake_upload_all)
    monkeypatch.setattr(burst_capture.time, 'sleep', lambda s: None)
    monkeypatch.setattr('builtins.input', lambda prompt="": "")
    monkeypatch.setattr(burst_capture, 'get_frame_quality_metrics', lambda p: {"brightness": 100.0, "laplacian_var": 50.0, "contrast_stddev": 30.0})

    test_args = [
        "burst_capture.py",
        "--count", "2",
        "--delay", "0.01",
        "--label", "unit_test",
        "--output-dir", str(out_dir),
        "--countdown", "0",
        "--workers", "2",
    ]
    monkeypatch.setattr(burst_capture.sys, "argv", test_args)

    burst_capture.main()

    assert len(uploaded) == 2
    assert out_dir.exists()


