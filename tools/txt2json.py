#!/usr/bin/env python3
import sys
from results2json.cli import main

if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--allow-txt" not in argv:
        argv = ["--allow-txt"] + argv
    raise SystemExit(main())