from merrill_monitor.fred import FredClient


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self):
        return {
            "observations": [
                {
                    "date": "2026-06-10",
                    "value": "4.33",
                }
            ]
        }


class FakeSession:
    def get(self, *args, **kwargs):
        return FakeResponse()


def test_fred_skips_when_api_key_missing() -> None:
    client = FredClient(api_key="")

    assert client.latest_observations(source_name="fred_rates", series=[{"id": "DFF"}]) == []


def test_fred_latest_observation_candidate() -> None:
    client = FredClient(api_key="test-key")
    client.session = FakeSession()

    candidates = client.latest_observations(
        source_name="fred_rates",
        series=[{"id": "DFF", "label": "Effective Federal Funds Rate"}],
    )

    assert len(candidates) == 1
    assert candidates[0].metadata["source_kind"] == "fred_series"
    assert candidates[0].published_date == "2026-06-10"
    assert "monitor_sig=" in candidates[0].normalized_url
