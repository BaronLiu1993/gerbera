from gerbera_cli.setup import generate_secret


def test_generate_secret_returns_distinct_values() -> None:
    first_secret = generate_secret()
    second_secret = generate_secret()

    assert first_secret != second_secret
