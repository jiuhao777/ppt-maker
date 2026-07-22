from pathlib import Path

from pptmaker.m0.parser_probe import generate_parser_fixtures


if __name__ == "__main__":
    generate_parser_fixtures(Path(__file__).parent)
