"""
llm_file_assistant.py - Natural-language interface over fs_tools using
OpenRouter (OpenAI-compatible API) with tool calling.

Usage:
  export OPENROUTER_API_KEY=...
  export OPENROUTER_MODEL=<a free model ID with tool support>
  python llm_file_assistant.py                                  # interactive
  python llm_file_assistant.py "Read all resumes in ./resumes"  # one-shot
"""

from __future__ import annotations

import json
import os
import sys

from openai import OpenAI

from fs_tools import TOOL_FUNCTIONS, TOOL_SCHEMAS

BASE_URL = "https://openrouter.ai/api/v1"
MODEL = os.getenv("OPENROUTER_MODEL", "")
MAX_TOOL_ROUNDS = 10          # safety cap on the tool-calling loop
MAX_RESULT_CHARS = 20_000     # keep giant tool results from blowing up context

SYSTEM_PROMPT = """You are a file system assistant that helps users work with resume files.

Guidelines:
- Use list_files to discover files before reading them. Default resume folder is ./resumes.
- Use read_file to get resume content. Use search_in_file for targeted keyword questions.
- When asked to create a summary, read the source file first, then write a concise
  summary (name, title, years of experience, key skills, education) using write_file.
  Save summaries to ./summaries/<source_stem>_summary.txt unless the user specifies a path.
- If a tool returns an error, explain it plainly and suggest a fix.
- Keep final answers concise and well organized. Name the files you used."""


def to_openai_tools(schemas: list[dict]) -> list[dict]:
    """Convert our tool schemas to the OpenAI/OpenRouter function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s["description"],
                "parameters": s["input_schema"],
            },
        }
        for s in schemas
    ]


OPENAI_TOOLS = to_openai_tools(TOOL_SCHEMAS)


def execute_tool(name: str, args: dict) -> dict:
    """Run a tool by name and wrap the result in a uniform, JSON-safe envelope."""
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return {"success": False, "error": f"Unknown tool: {name}"}

    try:
        result = func(**args)
    except TypeError as exc:
        return {"success": False, "error": f"Invalid arguments for {name}: {exc}"}
    except Exception as exc:
        return {"success": False, "error": f"{name} failed: {exc}"}

    if isinstance(result, list):  # list_files returns a bare list
        return {"success": True, "count": len(result), "items": result}
    return result


def serialize_result(result: dict) -> str:
    """Convert a tool result to a string for the model, truncating if huge."""
    text = json.dumps(result, default=str, ensure_ascii=False)
    if len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + "\n...[truncated]"
    return text


def run_query(client: OpenAI, user_query: str, history: list) -> str:
    """Send a query, run any requested tools, and return the final text answer."""
    history.append({"role": "user", "content": user_query})

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=history,
            tools=OPENAI_TOOLS,
            max_tokens=2048,
        )
        msg = response.choices[0].message

        # Store the assistant turn, including any tool calls, so the model sees its own requests
        assistant_msg = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        history.append(assistant_msg)

        # No tool requests means this is the final answer
        if not msg.tool_calls:
            return (msg.content or "").strip()

        for tc in msg.tool_calls:
            print(f"  [tool] {tc.function.name}({tc.function.arguments})")
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                result = {"success": False, "error": "Tool arguments were not valid JSON"}
            else:
                result = execute_tool(tc.function.name, args)

            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": serialize_result(result),
            })

    return "Stopped: the assistant hit the tool-call limit before finishing."


def main() -> None:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        sys.exit("Error: set the OPENROUTER_API_KEY environment variable first.")
    if not MODEL:
        sys.exit("Error: set OPENROUTER_MODEL to a free model ID that supports tools.")

    client = OpenAI(base_url=BASE_URL, api_key=api_key)
    history: list = [{"role": "system", "content": SYSTEM_PROMPT}]

    # One-shot mode: python llm_file_assistant.py "your query"
    if len(sys.argv) > 1:
        print(run_query(client, " ".join(sys.argv[1:]), history))
        return

    print("LLM File Assistant (type 'exit' to quit)")
    print("Try: 'Read all resumes in the resumes folder'")
    print("     'Find resumes mentioning Python experience'")
    print("     'Create a summary file for resume_john_doe.pdf'\n")

    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if query.lower() in {"exit", "quit"}:
            break
        if not query:
            continue
        print(f"\nAssistant: {run_query(client, query, history)}\n")


if __name__ == "__main__":
    main()
