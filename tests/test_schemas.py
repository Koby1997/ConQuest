import pytest
from pydantic import ValidationError

from conquest.schemas import EventBatch, format_validation_error


def _errors(raw: dict) -> str:
    with pytest.raises(ValidationError) as caught:
        EventBatch.model_validate(raw)
    return format_validation_error(caught.value)


def test_sample_batch_is_valid(sample_batch):
    batch = EventBatch.model_validate(sample_batch)
    assert len(batch.series) == 2
    assert batch.series[0].occurrences[0].date_status == "estimated"


def test_errors_name_the_exact_field(sample_batch):
    sample_batch["series"][1]["occurrences"][0]["start_date"] = "2027-13-01"
    sample_batch["series"][0]["categories"] = ["cooking"]

    text = _errors(sample_batch)

    assert "series[1].occurrences[0].start_date" in text
    assert "series[0].categories[0]" in text
    assert "'cooking'" in text


def test_end_before_start_is_rejected(sample_batch):
    occurrence = sample_batch["series"][1]["occurrences"][0]
    occurrence["start_date"], occurrence["end_date"] = "2027-05-23", "2027-05-20"

    assert "end_date 2027-05-20 is before start_date 2027-05-23" in _errors(sample_batch)


def test_price_range_must_be_ordered(sample_batch):
    sample_batch["series"][1]["occurrences"][0].update(price_min=100, price_max=20)

    assert "price_max 20.0 is less than price_min 100.0" in _errors(sample_batch)


def test_urls_must_be_full_links(sample_batch):
    sample_batch["series"][0]["website"] = "example.com"
    sample_batch["series"][0]["review_sources"] = ["reddit thread"]

    text = _errors(sample_batch)

    assert "series[0].website" in text
    assert "series[0].review_sources[0]" in text


def test_empty_website_becomes_none(sample_batch):
    sample_batch["series"][0]["website"] = "  "
    assert EventBatch.model_validate(sample_batch).series[0].website is None


def test_unknown_fields_are_rejected(sample_batch):
    sample_batch["series"][0]["rating"] = 5

    assert "series[0].rating: Extra inputs are not permitted" in _errors(sample_batch)


def test_unknown_region_is_rejected(sample_batch):
    sample_batch["regions_searched"] = ["Gulf Coast"]

    assert "unknown region" in _errors(sample_batch)


def test_state_is_uppercased(sample_batch):
    sample_batch["series"][1]["occurrences"][0]["state"] = "fl"
    assert EventBatch.model_validate(sample_batch).series[1].occurrences[0].state == "FL"
