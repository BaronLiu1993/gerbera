import subprocess



def create_tunnel(port: int = 8000) -> None:
    command = ["ngrok", "http", str(port)]
    subprocess.run(command, check=True)
