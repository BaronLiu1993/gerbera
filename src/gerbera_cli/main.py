
import typer

from gerbera_cli.initialise.initialise import init
from gerbera_cli.setup.setup import setup
from gerbera_cli.deploy.deploy import deploy

app = typer.Typer()

app.command(name="init")(init)
app.command(name="setup")(setup)
app.command(name="deploy")(deploy)

def main():
    app()

if __name__ == "__main__":
    main()
