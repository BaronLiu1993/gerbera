def append_message(
    messages: list[dict[str, object]],
    *,
    role: str,
    content: str | None = None,
    **fields: object,
) -> None:
    message: dict[str, object] = {"role": role}
    if content is not None:
        message["content"] = content
    message.update(fields)
    messages.append(message)
