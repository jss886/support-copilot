from cli.args import parse_args
from cli.handlers import run_command


def main() -> None:
    args = parse_args()
    run_command(args)
