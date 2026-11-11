
import sys
from pathlib import Path

import veil_lang


def main():
    if len(sys.argv) < 2:
        print("Usage: VeilTerminal.exe program.veil")
        input("Press Enter to exit...")
        return

    path = Path(sys.argv[1])

    try:
        source = path.read_text(encoding="utf-8")
        veil_lang.run_source(source, max_steps=None)

    except KeyboardInterrupt:
        print("\nInterrupted.")

    except Exception as exc:
        print(f"\nVeil error: {type(exc).__name__}: {exc}")

    finally:
        print("\n\nGame finished.")
        input("Press Enter to close this terminal...")


if __name__ == "__main__":
    main()