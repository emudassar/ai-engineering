import json
import os
import random
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from groq import Groq
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

# uv add langgraph langchain-core groq python-dotenv
load_dotenv()

groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "openai/gpt-oss-20b"

# ============================================================
# MENU (placeholder - replace once the real menu is decided)
# ============================================================

MENU = {
    "pizza": 5,
    "burger": 10,
    "pasta": 3,
    "biryani": 0,
}

COOK_FAIL_PROB = 0.4
SERVE_FAIL_PROB = 0.4  # not specified in the prompt, assumed same as cook


# ============================================================
# STATE
# ============================================================

class OrderState(TypedDict):
    messages: Annotated[list, add_messages]

    # order details
    dish_name: str
    required_qty: int
    available_qty: int

    # PENDING | CONFIRMED | PARTIAL | UNAVAILABLE | READY | COMPLETE | FAILED
    status: str

    # a counter hitting 0 means that stage is out of attempts
    order_retries: int
    cook_retries: int
    serve_retries: int

    final_result: str


# ============================================================
# LLM HELPERS
# ============================================================

PARSE_PROMPT = """You are the input parser of a restaurant ordering agent.
Return ONLY JSON: {"intent": "...", "dish": "...", "quantity": 0}

intent is one of:
- "order": user is ordering a dish (fill dish in lowercase singular, and quantity as int, default 1)
- "confirm": user agrees to go ahead with the partial order offered
- "decline": user refuses / cancels / does not want to continue
- "unrelated": anything not about food ordering
{context}"""


def parse_input(text: str, context: str = "") -> dict:
    response = groq.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": PARSE_PROMPT.format(context=context)},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        return {"intent": "unrelated", "dish": "", "quantity": 0}


def say(state: OrderState, instruction: str) -> AIMessage:
    """Let the LLM write a user-facing message, grounded in the current state."""
    snapshot = {
        k: state.get(k)
        for k in (
            "dish_name", "required_qty", "available_qty", "status",
            "order_retries", "cook_retries", "serve_retries",
        )
    }
    response = groq.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a friendly restaurant ordering agent. You ONLY handle "
                    "food orders; you are not a general purpose assistant. Write a "
                    "short message to the customer. Base it strictly on this state: "
                    f"{json.dumps(snapshot)}"
                ),
            },
            {"role": "user", "content": instruction},
        ],
    )
    text = response.choices[0].message.content
    print(f"\nAgent: {text}")
    return AIMessage(content=text)


# ============================================================
# NODES
# ============================================================

def get_order(state: OrderState):
    text = input("\nYou: ")
    parsed = parse_input(text)

    update = {"messages": [HumanMessage(content=text)]}

    if parsed["intent"] != "order":
        # refuse and wait for a real order; does not consume an order retry
        update["status"] = "NO_ORDER"
        update["messages"].append(say(
            state,
            "The user's message is not a food order. Politely say you are an AI "
            "agent for food ordering, not a general purpose assistant.",
        ))
        return update

    update["dish_name"] = parsed["dish"].lower().strip()
    update["required_qty"] = int(parsed["quantity"] or 1)
    update["status"] = "PENDING"
    return update


def order_confirm(state: OrderState):
    available = MENU.get(state["dish_name"], 0)
    required = state["required_qty"]

    if available >= required:
        status = "CONFIRMED"
    elif available > 0:
        status = "PARTIAL"
    else:
        status = "UNAVAILABLE"

    update = {"available_qty": available, "status": status}
    if status != "CONFIRMED":
        update["order_retries"] = state["order_retries"] - 1
    return update


def ask_user(state: OrderState):
    """Order was partial/unavailable: tell the user and let them decide."""
    if state["status"] == "PARTIAL":
        instruction = (
            "Tell the user we only have part of what they asked for. Ask if they "
            "want to go ahead with the available quantity or place a new order."
        )
    else:
        instruction = (
            "Tell the user the dish is not available. Ask if they want to order "
            "something else."
        )
    msg = say(state, instruction)

    text = input("\nYou: ")
    context = (
        f'We offered {state["available_qty"]} x {state["dish_name"]}. '
        'If the user accepts the offer, intent is "confirm".'
        if state["status"] == "PARTIAL" else ""
    )
    parsed = parse_input(text, context)
    messages = [msg, HumanMessage(content=text)]

    if parsed["intent"] == "confirm" and state["status"] == "PARTIAL":
        return {
            "messages": messages,
            "required_qty": state["available_qty"],
            "status": "CONFIRMED",
        }
    if parsed["intent"] == "order":
        return {
            "messages": messages,
            "dish_name": parsed["dish"].lower().strip(),
            "required_qty": int(parsed["quantity"] or 1),
            "status": "PENDING",
        }
    # decline / unrelated
    return {
        "messages": messages,
        "status": "FAILED",
        "final_result": "Order cancelled by the user.",
    }


def cook(state: OrderState):
    if random.random() < COOK_FAIL_PROB:
        print("[cook] failed")
        return {"cook_retries": state["cook_retries"] - 1, "status": "CONFIRMED"}
    print("[cook] success")
    return {"status": "READY"}


def serve(state: OrderState):
    if random.random() < SERVE_FAIL_PROB:
        print("[serve] failed")
        serve_left = state["serve_retries"] - 1
        update = {"serve_retries": serve_left, "status": "SERVE_FAILED"}
        # retrying means cooking again, which uses up a cook retry
        if serve_left > 0 and state["cook_retries"] > 0:
            update["cook_retries"] = state["cook_retries"] - 1
            update["status"] = "CONFIRMED"
        return update
    print("[serve] success")
    return {"status": "COMPLETE"}


def complete(state: OrderState):
    msg = say(state, "Tell the user their order is complete. Mention dish and quantity.")
    return {
        "messages": [msg],
        "final_result": f"COMPLETED: {state['required_qty']} x {state['dish_name']}",
    }


def apologize(state: OrderState):
    if state["order_retries"] <= 0 and state["status"] in ("PARTIAL", "UNAVAILABLE"):
        reason = "we could not match the user's order to the menu after 3 attempts"
    elif state["cook_retries"] <= 0:
        reason = "the kitchen failed to cook the order"
    else:
        reason = "the order could not be served"
    msg = say(state, f"Apologise sincerely: {reason}.")
    return {
        "messages": [msg],
        "status": "FAILED",
        "final_result": f"NOT COMPLETED: {reason}",
    }


# ============================================================
# ROUTING
# ============================================================

def after_get_order(state: OrderState):
    return "get_order" if state["status"] == "NO_ORDER" else "order_confirm"


def after_order_confirm(state: OrderState):
    if state["status"] == "CONFIRMED":
        return "cook"
    return "apologize" if state["order_retries"] <= 0 else "ask_user"


def after_ask_user(state: OrderState):
    if state["status"] == "FAILED":
        return END
    # CONFIRMED (accepted partial) skips re-checking the menu
    return "cook" if state["status"] == "CONFIRMED" else "order_confirm"


def after_cook(state: OrderState):
    if state["status"] == "READY":
        return "serve"
    return "apologize" if state["cook_retries"] <= 0 else "cook"


def after_serve(state: OrderState):
    if state["status"] == "COMPLETE":
        return "complete"
    # serve failed -> cook again, unless serve or cook is out of retries
    return "cook" if state["status"] == "CONFIRMED" else "apologize"


# ============================================================
# GRAPH
# ============================================================

def build_graph():
    g = StateGraph(OrderState)
    for fn in (get_order, order_confirm, ask_user, cook, serve, complete, apologize):
        g.add_node(fn.__name__, fn)

    g.add_edge(START, "get_order")
    g.add_conditional_edges("get_order", after_get_order, ["get_order", "order_confirm"])
    g.add_conditional_edges(
        "order_confirm", after_order_confirm, ["cook", "ask_user", "apologize"]
    )
    g.add_conditional_edges(
        "ask_user", after_ask_user, ["cook", "order_confirm", END]
    )
    g.add_conditional_edges("cook", after_cook, ["serve", "cook", "apologize"])
    g.add_conditional_edges(
        "serve", after_serve, ["complete", "cook", "apologize"]
    )
    g.add_edge("complete", END)
    g.add_edge("apologize", END)
    return g.compile()


def initial_state() -> OrderState:
    return {
        "messages": [],
        "dish_name": "",
        "required_qty": 0,
        "available_qty": 0,
        "status": "PENDING",
        "order_retries": 3,
        "cook_retries": 2,
        "serve_retries": 2,
        "final_result": "",
    }


def main():
    print("=" * 60)
    print("RESTAURANT ORDER AGENT")
    print("=" * 60)
    final = build_graph().invoke(initial_state())
    print(f"\nFINAL RESULT: {final['final_result']}")


if __name__ == "__main__":
    main()
