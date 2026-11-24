from importlib.resources import files


DATABASE_NAME = "gerbera_db"

TABLE_CONFIGURATION = {
    "hw201": "discrete.sql",
    "ky033": "discrete.sql",
    "hcsr04": "continuous.sql",
}


def load_table_sql(component_type: str) -> str:
    filename = TABLE_CONFIGURATION[component_type]
    path = files("gerbera_sdk.config").joinpath("sql", filename)
    return path.read_text(encoding="utf-8")
