def local_server_config(port: str = "8000", host: str = "127.0.0.1") -> dict:
    return {
        "type": "local",
        "connection_url": f"http://{host}:{port}/mcp",
    }


# Ngrok support later:
# def public_server_config(public_endpoint: str) -> dict:
#     return {
#         "type": "ngrok",
#         "connection_url": f"{public_endpoint.rstrip('/')}/mcp",
#     }
