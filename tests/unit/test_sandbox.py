from gerbera_harness.sandbox.sandbox_gateway import Sandbox
from gerbera_harness.sandbox.sandbox_gateway import SANDBOX_IMAGE


def test_sandbox_uses_built_container_image_name() -> None:
    sandbox = Sandbox(session_id="session")

    assert sandbox.container_image == SANDBOX_IMAGE
    assert sandbox.container_image == "gerbera-python-sandbox:latest"
