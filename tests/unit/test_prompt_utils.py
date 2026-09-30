from gerbera_harness.prompts import PromptTypeEnum, load_prompt


def test_load_prompt_reads_main_prompt() -> None:
    prompt = load_prompt(PromptTypeEnum.MAIN, "TASK_DECOMPOSITION.md")

    assert prompt.startswith("## Role")


def test_load_prompt_reads_sub_prompt() -> None:
    prompt = load_prompt(PromptTypeEnum.SUB, "PLANNING.md")

    assert prompt.startswith("# Planning")


def test_task_decomposition_prompt_keeps_tasks_non_executable() -> None:
    prompt = load_prompt(PromptTypeEnum.MAIN, "TASK_DECOMPOSITION.md")

    assert "Tasks are high-level instructions" in prompt
    assert "- Operate hardware." in prompt
    assert "- Generate nested action groups." in prompt


def test_planning_prompt_defines_continuous_action_boundaries() -> None:
    prompt = load_prompt(PromptTypeEnum.SUB, "PLANNING.md")

    assert "Use continuous actions only when" in prompt
    assert "must later be reversed" in prompt


def test_observation_prompt_only_allows_read_only_tools() -> None:
    prompt = load_prompt(PromptTypeEnum.SUB, "OBSERVE.md")

    assert "Only read-only tools are available" in prompt
    assert "Do not command actuators" in prompt
    assert "Do not invent" in prompt
