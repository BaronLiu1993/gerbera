import typer

# Subcommands
from gerbera_cli.initialise.initialise import init_app

app = typer.Typer()

app.add_typer(init_app, help="")

def main():
    app()

if __name__ == "__main__":
    main()