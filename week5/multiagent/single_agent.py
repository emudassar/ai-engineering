from multiagent import CALC_TOOL, SEARCH_TOOL, TASK, Usage, run_agent


def single_agent(task):
    usage = Usage()
    answer = run_agent(
        "single_agent",
        "You are a helpful assistant. Use web_search for facts and calculator for any math.",
        task, [SEARCH_TOOL, CALC_TOOL], usage,
    )
    print("\nFinal answer:\n", answer)
    return usage.report("single agent")


if __name__ == "__main__":
    print("Task:", TASK)
    single_agent(TASK)
