from merrill_monitor.cfpb import CFPBComplaintsClient, extract_complaint_records


def test_extract_complaint_records_supports_value_shape() -> None:
    payload = {
        "value": [
            {
                "complaint_id": "123",
                "company": "BANK OF AMERICA",
                "product": "Checking or savings account",
            }
        ]
    }

    records = extract_complaint_records(payload)

    assert records == payload["value"]


def test_extract_complaint_records_supports_hits_shape() -> None:
    payload = {
        "hits": {
            "hits": [
                {
                    "_id": "abc",
                    "_source": {
                        "company": "MERRILL LYNCH",
                        "product": "Money transfer",
                    },
                }
            ]
        }
    }

    records = extract_complaint_records(payload)

    assert records[0]["_id"] == "abc"
    assert records[0]["company"] == "MERRILL LYNCH"


def test_cfpb_candidate_uses_complaint_detail_url() -> None:
    client = CFPBComplaintsClient()
    candidate = client._to_candidate(
        source_name="cfpb_merrill_complaints",
        record={
            "complaint_id": "999",
            "company": "MERRILL EDGE",
            "product": "Investment account",
            "issue": "Trouble transferring account",
            "complaint_what_happened": "The transfer took too long.",
            "date_received": "2026-06-10",
        },
    )

    assert candidate is not None
    assert candidate.metadata["source_kind"] == "cfpb_complaints"
    assert candidate.published_date == "2026-06-10"
    assert candidate.url.endswith("/999")
