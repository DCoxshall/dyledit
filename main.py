#!/usr/bin/env python3

from editor import Editor
import sys


def main():
    E = Editor()
    E.enableRawMode()
    if len(sys.argv) == 2:
        try:
            E.openFile(sys.argv[1])
        except Exception as e:

            E.die(str(e))
    E.setStatusMessage("HELP: Ctrl-S = save | Ctrl-Q = quit | Ctrl-F = find")

    while True:
        E.refreshScreen()
        E.processKeyPress()


if __name__ == "__main__":
    main()
