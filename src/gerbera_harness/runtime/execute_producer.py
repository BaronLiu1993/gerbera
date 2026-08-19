class ExecuteProducer:
    model: Model
    memory: Memory
    tool_client: ToolClient
    max_attempts: int = 3

    