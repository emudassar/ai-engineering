import ast
import json
import operator
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from groq import Groq

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
MODEL = "openai/gpt-oss-120b"
MAX_ATTEMPTS = 5

TASK = (
    "Find the current population of Japan and the current population of Germany "
    "using web search. Then calculate how many times larger Japan's population is "
    "than Germany's, and what the combined population of both countries is."
)


# ---------- token tracking ----------
class Usage:
    def __init__(self):
        self.by_agent = {}

    def add(self, agent, usage):
        s = self.by_agent.setdefault(agent, {"calls": 0, "prompt": 0, "completion": 0, "total": 0})
        s["calls"] += 1
        s["prompt"] += usage.prompt_tokens
        s["completion"] += usage.completion_tokens
        s["total"] += usage.total_tokens

    def report(self, title):
        print(f"\n===== Token usage: {title} =====")
        totals = {"calls": 0, "prompt": 0, "completion": 0, "total": 0}
        for agent, s in self.by_agent.items():
            print(f"{agent:<18} calls={s['calls']:<3} prompt={s['prompt']:<6} "
                  f"completion={s['completion']:<6} total={s['total']}")
            for k in totals:
                totals[k] += s[k]
        print(f"{'TOTAL':<18} calls={totals['calls']:<3} prompt={totals['prompt']:<6} "
              f"completion={totals['completion']:<6} total={totals['total']}")
        return totals


# ---------- tools ----------
def web_search(query):
    r = requests.post(
        "https://api.tavily.com/search",
        json={"api_key": TAVILY_API_KEY, "query": query, "max_results": 3, "include_answer": True},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    lines = [f"Answer: {data.get('answer')}"]
    for item in data.get("results", []):
        lines.append(f"- {item['title']}: {item['content'][:300]} ({item['url']})")
    return "\n".join(lines)


_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported expression")


def calculator(expression):
    return str(_eval(ast.parse(expression, mode="eval").body))


def tool_schema(name, description, param, param_desc):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {param: {"type": "string", "description": param_desc}},
                "required": [param],
            },
        },
    }


SEARCH_TOOL = tool_schema("web_search", "Search the web for current information.", "query", "The search query")
CALC_TOOL = tool_schema("calculator", "Evaluate an arithmetic expression, e.g. '(3+4)*2/5'.",
                        "expression", "The arithmetic expression")
FUNCS = {"web_search": web_search, "calculator": calculator}


# ---------- generic agent loop ----------
def run_agent(name, system, task, tools, usage, extra_funcs=None, max_attempts=MAX_ATTEMPTS):
    """Tool-calling loop. Each LLM call counts as one attempt; stops after max_attempts."""
    funcs = {**FUNCS, **(extra_funcs or {})}
    messages = [{"role": "system", "content": system}, {"role": "user", "content": task}]

    for attempt in range(1, max_attempts + 1):
        resp = client.chat.completions.create(model=MODEL, messages=messages, tools=tools)
        usage.add(name, resp.usage)
        msg = resp.choices[0].message

        if not msg.tool_calls:
            return msg.content

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        })
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            print(f"[{name}] attempt {attempt}: {tc.function.name}({args})")
            try:
                result = funcs[tc.function.name](**args)
            except Exception as e:
                result = f"Error: {e}"
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    return f"[{name}] stopped: reached max attempts ({max_attempts}) without a final answer."


# ---------- multi agent (manager + 2 workers, no langgraph) ----------
def multi_agent(task):
    usage = Usage()

    def ask_search_agent(request):
        print(f"[manager] -> search_agent: {request}")
        return run_agent(
            "search_agent",
            "You are a research agent. Use web_search to find the requested facts and reply "
            "concisely with the figures and their sources.",
            request, [SEARCH_TOOL], usage,
        )

    def ask_calculator_agent(request):
        print(f"[manager] -> calculator_agent: {request}")
        return run_agent(
            "calculator_agent",
            "You are a math agent. Use the calculator tool for every computation and reply "
            "concisely with the results.",
            request, [CALC_TOOL], usage,
        )

    manager_tools = [
        tool_schema("ask_search_agent", "Delegate a fact-finding / web research request to the search agent.",
                    "request", "What to look up, fully self-contained"),
        tool_schema("ask_calculator_agent", "Delegate a calculation to the calculator agent. Include the numbers.",
                    "request", "The calculation to perform, with all numbers included"),
    ]
    answer = run_agent(
        "manager",
        "You are a manager. You have no tools of your own except delegating. Break the task into "
        "steps, send research to ask_search_agent and math to ask_calculator_agent, then combine "
        "their results into the final answer.",
        task, manager_tools, usage,
        extra_funcs={"ask_search_agent": ask_search_agent, "ask_calculator_agent": ask_calculator_agent},
    )
    print("\nFinal answer:\n", answer)
    return usage.report("multi agent")


if __name__ == "__main__":
    print("Task:", TASK)
    multi_agent(TASK)


def main():
    pass
