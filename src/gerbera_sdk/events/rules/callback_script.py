import ast
from textwrap import dedent, indent


RULE_CALLBACK_IMPORTS = (
    "import httpx\n"
    "from fastmcp import Client"
)
RULE_CALLBACK_HEADER = "async def callback(mcp_url, value):"
RULE_CALLBACK_PARAMETERS = frozenset({"mcp_url", "value"})


def normalize_rule_callback_body(callback_body: str) -> str:
    normalized_body = dedent(callback_body).strip()
    if not normalized_body:
        raise ValueError("Rule callback body cannot be empty")

    callback_script = (
        f"{RULE_CALLBACK_HEADER}\n"
        f"{indent(normalized_body, '    ')}\n"
    )

    try:
        module = ast.parse(callback_script, mode="exec")
    except SyntaxError as exc:
        raise ValueError(
            f"Rule callback body is not valid Python: {exc.msg}"
        ) from exc

    callback = module.body[0]
    if not isinstance(callback, ast.AsyncFunctionDef):
        raise ValueError("Rule callback must be an async function")

    forbidden_nodes = (
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.FunctionDef,
        ast.Import,
        ast.ImportFrom,
        ast.Yield,
        ast.YieldFrom,
    )
    for statement in callback.body:
        if any(
            isinstance(node, forbidden_nodes)
            for node in ast.walk(statement)
        ):
            raise ValueError(
                "Rule callback body cannot define functions or classes, "
                "contain imports, or yield"
            )

    reassigned_parameters = {
        node.id
        for statement in callback.body
        for node in ast.walk(statement)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Store)
        and node.id in RULE_CALLBACK_PARAMETERS
    }
    if reassigned_parameters:
        names = ", ".join(sorted(reassigned_parameters))
        raise ValueError(
            f"Rule callback body cannot reassign injected parameters: {names}"
        )

    return normalized_body


def build_rule_callback_script(callback_body: str) -> str:
    normalized_body = normalize_rule_callback_body(callback_body)
    return (
        f"{RULE_CALLBACK_IMPORTS}\n\n\n"
        f"{RULE_CALLBACK_HEADER}\n"
        f"{indent(normalized_body, '    ')}\n"
    )
