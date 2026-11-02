"""CLI entry point for Agent 6 — Jarvis.

Usage:
    python main.py               # typed input, spoken + printed output
    python main.py --voice       # spoken input AND output — continuous conversation
    python main.py --mute "..."  # single query, printed only, no TTS
    python main.py "play some coldplay"   # single typed query, then exit

Interactive modes keep one thread_id for the whole session, so Jarvis
remembers earlier turns ("play something else" refers to the last request).
Say/type "stop", "quit", "exit", or "goodbye" to end a session.
"""

import sys
import uuid

from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

from agent.graph import build_graph  # noqa: E402  (import after load_dotenv)
from agent.voice import listen, speak  # noqa: E402

STOP_WORDS = {"stop", "quit", "exit", "goodbye"}


def ask(graph, config: dict, message: str) -> str:
    final_message = None
    for event in graph.stream(
        {"messages": [("user", message)]},
        config=config,
        stream_mode="values",
    ):
        final_message = event["messages"][-1]
    return final_message.content if final_message else ""


def converse(graph, config: dict) -> None:
    """Continuous two-way voice loop: listen, think, speak, repeat."""
    print("Jarvis is listening. Say 'stop' to end.")
    speak("I'm listening.")
    while True:
        message = listen()
        if message is None:
            continue  # silence or unrecognised — just listen again
        print(f"> {message}")
        if message.strip().lower() in STOP_WORDS:
            speak("Goodbye.")
            break
        reply = ask(graph, config, message)
        print(reply)
        speak(reply)


def main() -> None:
    args = sys.argv[1:]
    mute = "--mute" in args
    if mute:
        args.remove("--mute")
    voice_mode = "--voice" in args
    if voice_mode:
        args.remove("--voice")

    graph = build_graph()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    def respond(message: str) -> None:
        reply = ask(graph, config, message)
        print(reply)
        if not mute:
            speak(reply)

    if args:
        respond(args[0])
        return

    if voice_mode:
        converse(graph, config)
        return

    print("Jarvis is listening. Type your request (or 'quit' to exit).")
    while True:
        try:
            message = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not message or message.lower() in {"quit", "exit"}:
            break
        respond(message)


if __name__ == "__main__":
    main()
