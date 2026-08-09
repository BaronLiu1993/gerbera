import subprocess

# Docker config values
GERBERA_IMAGE = "ghcr.io/baronliu1993/gerbera:latest"
POSTGRES_IMAGE = "ghcr.io/baronliu1993/gerbera-postgres:latest"
NETWORK = "gerbera"
POSTGRES_CONTAINER = "gerbera-postgres"
HARNESS_CONTAINER = "gerbera-harness"
POSTGRES_VOLUME = "gerbera_postgres_data"

def run_local_harness():
    subprocess.run(["docker", "pull", GERBERA_IMAGE], check=True)
    subprocess.run(["docker", "pull", POSTGRES_IMAGE], check=True)
    subprocess.run(["docker", "network", "create", NETWORK], check=False)
    subprocess.run(["docker", "volume", "create", POSTGRES_VOLUME], check=True)
    subprocess.run(["docker", "rm", "-f", POSTGRES_CONTAINER], check=False)
    subprocess.run(["docker", "rm", "-f", HARNESS_CONTAINER], check=False)
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            POSTGRES_CONTAINER,
            "--network",
            NETWORK,
            "-p",
            "6432:5432",
            "-e",
            "POSTGRES_DB=gerbera",
            "-e",
            "POSTGRES_USER=gerbera_admin",
            "-e",
            "POSTGRES_PASSWORD=gerbera_admin_password",
            "-v",
            f"{POSTGRES_VOLUME}:/var/lib/postgresql/data",
            POSTGRES_IMAGE,
        ],
        check=True,
    )
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            HARNESS_CONTAINER,
            "--network",
            NETWORK,
            "-p",
            "8000:8000",
            "-e",
            f"GERBERA_DATABASE_HOST={POSTGRES_CONTAINER}",
            "-e",
            "GERBERA_DATABASE_PORT=5432",
            "-e",
            "GERBERA_DATABASE_NAME=gerbera",
            "-e",
            "GERBERA_SCHEMA_USER=gerbera_schema_owner",
            "-e",
            "GERBERA_SCHEMA_PASSWORD=schema_password",
            "-e",
            "GERBERA_WRITER_USER=gerbera_writer",
            "-e",
            "GERBERA_WRITER_PASSWORD=writer_password",
            "-e",
            "GERBERA_READER_USER=gerbera_reader",
            "-e",
            "GERBERA_READER_PASSWORD=reader_password",
            GERBERA_IMAGE,
        ],
        check=True,
    )
