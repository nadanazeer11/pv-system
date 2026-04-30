"""Shared pytest fixtures."""
import pandas as pd
import pytest


@pytest.fixture
def fake_tmy() -> pd.DataFrame:
    """Synthetic TMY DataFrame for tests.

    Constant irradiance, temperature and wind across 8760 hours so that
    summary statistics have known closed-form values.
    """
    idx = pd.date_range("2020-01-01", periods=8760, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "ghi": [500.0] * 8760,
            "dni": [600.0] * 8760,
            "dhi": [200.0] * 8760,
            "temp_air": [25.0] * 8760,
            "wind_speed": [3.0] * 8760,
        },
        index=idx,
    )
