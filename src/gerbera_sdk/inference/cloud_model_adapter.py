from enum import Enum
import cv2

from gerbera_sdk.models.hardware.camera import Frame

class ModelProviderEnum(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


class CloudModelAdapter(ModelAdapter):
    def convert_to_valid_input(self, frame: Frame) -> str:
        success, encoded = cv2.imencode(
            ".jpg",
            frame.image,
            [cv2.IMWRITE_JPEG_QUALITY, 90],
        )
        if not success:
            raise RuntimeError("Could not encode camera frame")

        base64_image = base64.b64encode(encoded.tobytes()).decode("ascii")
        return f"data:image/jpeg;base64,{base64_image}"

    @abstractmethod
    def predict(self, model_input: object) -> object:
        """Send converted input to an API-backed model."""
