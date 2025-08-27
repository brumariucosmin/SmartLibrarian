import sys

from app.orchestrator import SmartLibrarian

BANNER = """
Smart Librarian (CLI)
Type your question in Romanian. Type 'exit' to quit.
"""

def main():
    print(BANNER)
    bot = SmartLibrarian()
    while True:
        try:
            q = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nLa revedere!")
            break
        if not q:
            continue
        if q.lower() in {"exit", "quit"}:
            print("La revedere!")
            break
        ans = bot.chat_once(q)
        print("\n" + ans + "\n")

if __name__ == "__main__":
    main()
