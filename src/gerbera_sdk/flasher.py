import subprocess

class Flasher:
    @staticmethod
    def flash(port: str, fqbn: str, sketch_path: str) -> None:
        subprocess.run([
            "arduino-cli", "compile",
            "--fqbn", fqbn,
            sketch_path
        ], check=True)

        subprocess.run([
            "arduino-cli", "upload",
            "-p", port,
            "--fqbn", fqbn,
            sketch_path
        ], check=True)