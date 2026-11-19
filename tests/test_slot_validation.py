import json
import glob
import os
import pytest
from validators.slot_validator import SlotValidator


def get_fixture_files():
    # Dynamically find all JSON files inside the fixtures folder
    fixture_dir = os.path.join(os.path.dirname(__file__), "../fixtures")
    return glob.glob(os.path.join(fixture_dir, "*.json"))


@pytest.mark.parametrize("filepath", get_fixture_files())
def test_slot_response_validation(filepath):
    filename = os.path.basename(filepath)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        pytest.fail(f"[{filename}] Failed to parse JSON file: {e}")

    validator = SlotValidator(filename, data)
    errors = validator.validate()

    if errors:
        error_report = "\n  - " + "\n  - ".join(errors)
        pytest.fail(f"\nValidation failed for fixture '{filename}' with {len(errors)} error(s):{error_report}")