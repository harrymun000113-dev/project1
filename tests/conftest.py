"""테스트는 항상 오프라인 데모 모드 + 격리된 임시 캐시 디렉터리로 실행한다.

`config` 모듈은 임포트 시점에 환경변수를 읽어 상수로 고정하므로, 여기서 환경변수를
세팅하는 코드가 어떤 테스트 모듈보다도 먼저 실행되어야 한다. conftest.py는 pytest가
테스트 파일들을 수집하기 전에 로드되므로 이 시점에 맞춰 둔다.
"""
import os
import tempfile

os.environ["BLUEOCEAN_DEMO_MODE"] = "1"
os.environ["BLUEOCEAN_CACHE_DIR"] = tempfile.mkdtemp(prefix="blueocean_test_cache_")
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret")

import pytest


@pytest.fixture()
def app():
    from blueocean import create_app

    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture()
def client(app):
    return app.test_client()
