#!/bin/env python

import sys
import argparse


sys.dont_write_bytecode = True


from geprotondl import main
from geprotondl import File


def run(argv: list[str]) -> None:
    exitcode: int = main(argv)
    if exitcode:
        sys.exit(exitcode)
    return None


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("Frontend script to run main program multiple times "
                     "with predefined set of options.\n\n"
                     "equivalent to:\n"
                     "  geprotondl -tq "
                     "&& geprotondl -sH "
                     "&& geprotondl -i "
                     "&& geprotondl -lH"),
        epilog="No other commandline arguments are forwarded to geprotondl.")

    folders = parser.add_argument_group(title="locations", description=None)

    folders.add_argument(
        "-D", "--dir", metavar="DIR", type=File,
        help=("folder to unpack  and install GE-Proton into, if not set here "
              "then default from geprotondl is used"))

    folders.add_argument(
        "-C", "--cache", metavar="DIR", type=File,
        help=("folder to save temporary cache files into, if not set here "
              "then default from geprotondl is used"))

    if argv is None:
        return parser.parse_args()
    else:
        return parser.parse_args(argv)


# Runs main program multiple times with predefined set of options.
if __name__ == "__main__":
    args = parse_arguments()
    folders = []
    if args.dir:
        folders.extend(["--dir", args.dir])
    if args.cache:
        folders.extend(["--cache", args.cache])

    run(["--test", "--quiet"] + folders)
    run(["--summary", "--human"] + folders)
    run(["--install"] + folders)
    run(["--list", "--human"] + folders)
