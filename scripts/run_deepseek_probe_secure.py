import getpass
import os

from pptmaker.m0.deepseek_probe import main


def run() -> int:
    key = getpass.getpass("DeepSeek API key (hidden): ").strip()
    if not key:
        raise SystemExit("DeepSeek API key is required")
    os.environ["DEEPSEEK_API_KEY"] = key
    try:
        print(main())
    finally:
        os.environ.pop("DEEPSEEK_API_KEY", None)
        key = ""
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
