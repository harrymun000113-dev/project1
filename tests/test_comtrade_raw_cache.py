import json
from unittest.mock import Mock, patch

import pandas as pd

import config
from blueocean.services import comtrade


def test_api_response_is_saved_before_preprocessing_and_reused(tmp_path):
    raw_row = {
        "reporterISO": "USA", "partnerISO": "WLD", "period": 2024,
        "primaryValue": 123, "sourceNote": "field omitted by tidy",
    }
    payload = {"data": [raw_row], "count": 1}
    response = Mock(status_code=200)
    response.json.return_value = payload

    with patch.object(comtrade, "RAW_CACHE_DIR", tmp_path), \
         patch.object(config, "COMTRADE_API_KEYS", ["test-key"]), \
         patch.object(comtrade, "_next_key", return_value="test-key"), \
         patch.object(comtrade.requests, "get", return_value=response) as get:
        result = comtrade._call_api("M", "all", 0, "870323", [2024])
        assert result["value"].tolist() == [123]
        assert get.call_count == 1

        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1
        saved = json.loads(files[0].read_text(encoding="utf-8"))
        assert saved["response"] == payload
        assert "sourceNote" in saved["response"]["data"][0]
        assert "Ocp-Apim-Subscription-Key" not in files[0].read_text(encoding="utf-8")

        config.COMTRADE_API_KEYS.clear()  # A saved response needs no credential or quota.
        with patch.object(comtrade, "_tidy", return_value=pd.DataFrame({"reprocessed": [1]})) as tidy:
            again = comtrade._call_api("M", "all", 0, "870323", [2024])
            assert again["reprocessed"].tolist() == [1]
            tidy.assert_called_once_with(payload["data"], "M")
        assert get.call_count == 1


def test_empty_success_response_is_cached(tmp_path):
    response = Mock(status_code=200)
    response.json.return_value = {"data": []}

    with patch.object(comtrade, "RAW_CACHE_DIR", tmp_path), \
         patch.object(config, "COMTRADE_API_KEYS", ["test-key"]), \
         patch.object(comtrade, "_next_key", return_value="test-key"), \
         patch.object(comtrade.requests, "get", return_value=response) as get:
        assert comtrade._call_api("M", 410, 0, "000001", [2024]).empty
        assert comtrade._call_api("M", 410, 0, "000001", [2024]).empty
        assert get.call_count == 1
