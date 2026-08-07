from gerbera_harness.sandbox.sandbox import Sandbox


def test_sandbox_writes_script_to_run_directory() -> None:
    sandbox = Sandbox()

    try:
        script_path = sandbox.write_script("print('hello')", "script.py")

        assert script_path == sandbox.run_dir / "script.py"
        assert script_path.read_text() == "print('hello')"
    finally:
        sandbox.cleanup()


def test_sandbox_cleanup_removes_ephemeral_directory() -> None:
    sandbox = Sandbox()
    run_dir = sandbox.run_dir

    sandbox.write_script("print('hello')", "script.py")
    sandbox.cleanup()

    assert not run_dir.exists()
