import os
import time

import pandas as pd

from blueocean.services.cache import parquet_cache


def test_shared_parquet_is_reused_after_local_cache_disappears(tmp_path):
    local = tmp_path / "local"
    shared = tmp_path / "shared"
    calls = []

    @parquet_cache(local, ttl=1, shared_dir=shared)
    def fetch(hs6):
        calls.append(hs6)
        return pd.DataFrame({"value": [42]})

    assert fetch("220299")["value"].tolist() == [42]
    assert len(calls) == 1
    assert len(list(shared.glob("*.parquet"))) == 1

    for path in local.glob("*.parquet"):
        path.unlink()

    old_timestamp = time.time() - 20 * 365 * 24 * 3600
    for path in shared.glob("*.parquet"):
        os.utime(path, (old_timestamp, old_timestamp))

    assert fetch("220299")["value"].tolist() == [42]
    assert len(calls) == 1


def test_share_filter_keeps_demo_results_out_of_shared_dir(tmp_path):
    shared = tmp_path / "shared"

    @parquet_cache(tmp_path / "local", ttl=1, shared_dir=shared,
                   share_if=lambda args, kwargs: args[1] is False)
    def fetch(hs6, demo):
        return pd.DataFrame({"value": [1]})

    fetch("220299", True)
    assert not shared.exists()

    fetch("220299", False)
    assert len(list(shared.glob("*.parquet"))) == 1


def test_existing_local_parquet_is_promoted_to_shared_dir(tmp_path):
    local = tmp_path / "local"
    shared = tmp_path / "shared"
    calls = []

    def fetch(hs6):
        calls.append(hs6)
        return pd.DataFrame({"value": [7]})

    parquet_cache(local, ttl=60)(fetch)("870323")
    assert len(calls) == 1

    parquet_cache(local, ttl=60, shared_dir=shared)(fetch)("870323")
    assert len(calls) == 1
    assert len(list(shared.glob("*.parquet"))) == 1
