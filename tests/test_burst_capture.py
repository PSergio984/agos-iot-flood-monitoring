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
    ok, fp, url = burst_capture.upload_to_cloudinary('test.jpg', '123', label='test')
    assert ok is True
    assert fp == 'test.jpg'
    assert url == 'https://cdn.example.com/test.jpg'

def test_upload_to_cloudinary_failure(monkeypatch):
    def fake_upload(filepath, folder, tags, context):
        raise RuntimeError('upload error')

    monkeypatch.setattr(burst_capture.cloudinary.uploader, 'upload', fake_upload)
    ok, fp, err = burst_capture.upload_to_cloudinary('test.jpg', '123', label='test')
    assert ok is False
    assert fp == 'test.jpg'
    assert 'upload error' in err

def test_upload_all_concurrent(monkeypatch, tmp_path):
    files = [str(tmp_path / f'img_{i}.jpg') for i in range(5)]
    for f in files:
        with open(f, 'w') as fh:
            fh.write('x')

    def fake_upload(filepath, session_id, label, cloud_folder):
        return True, filepath, 'https://cdn/ok.jpg'

    monkeypatch.setattr(burst_capture, 'upload_to_cloudinary', fake_upload)
    results = burst_capture.upload_all_concurrent(files, 'session1', label='raining', max_workers=2)
    assert len(results) == 5
    assert all(ok for ok, _, _ in results)

def test_run_countdown(monkeypatch):
    sleeps = []
    monkeypatch.setattr(burst_capture.time, 'sleep', lambda s: sleeps.append(s))
    burst_capture.run_countdown(3)
    assert len(sleeps) == 3
