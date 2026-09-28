import pandas as pd
import pytest

from blueocean.pipeline.respond import _row_to_json


@pytest.mark.parametrize("share", [0, 0.0000001234, 0.00049, 0.01234, 12.34, None])
def test_share_precision_survives_serialization(share):
    row = pd.Series({"rank": 1, "korea_share_pct": share, "top3_share_pct": share}, name="DEU")
    result = _row_to_json(row)
    assert result["korea_share_pct"] == share
    assert result["competitors"]["top3_share_pct"] == share


@pytest.mark.parametrize("amount", [1234.56, 0, 0.001, None])
def test_korean_import_amount_is_not_derived_from_rounded_share(amount):
    row = pd.Series({"rank": 1, "korea_import_usd": amount,
                     "korea_share_pct": 0, "market_size": 1e9}, name="DEU")
    assert _row_to_json(row)["korea_import_usd"] == amount
