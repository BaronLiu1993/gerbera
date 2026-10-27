import pytest
from pydantic import ValidationError

from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_schema import ObjectDetectionModelInputSchema


@pytest.mark.parametrize("width", ["640", True])
def test_schema_rejects_coerced_dimensions(width) -> None:
    with pytest.raises(ValidationError):
        ObjectDetectionModelInputSchema(width=width, height=480)


def test_schema_validates_field_assignment() -> None:
    dimensions = ObjectDetectionModelInputSchema(width=640, height=480)

    with pytest.raises(ValidationError):
        dimensions.height = True
