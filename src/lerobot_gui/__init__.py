"""LeRobot GUI: a local web GUI that builds and runs the lerobot commands."""

__version__ = "0.1.0"


def main() -> None:
    from .cli import main as cli_main

    cli_main()
