from gerbera_harness.sandbox.sandbox_gateway import Sandbox
from gerbera_harness.sandbox.sandbox_gateway import SANDBOX_IMAGE
from gerbera_harness.sandbox.sandbox_gateway import LOCAL_SANDBOX_IMAGE


def test_sandbox_uses_built_container_image_name() -> None:
    sandbox = Sandbox(session_id="session")

    assert SANDBOX_IMAGE == "ghcr.io/baronliu1993/gerbera-sandbox:latest"
    assert sandbox.container_image == LOCAL_SANDBOX_IMAGE
    assert sandbox.container_image == "gerbera-sandbox:latest"
