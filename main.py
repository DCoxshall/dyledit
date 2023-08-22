#!/usr/bin/env python3

from editor import Editor
import sys


def main():
    E = Editor()
    E.enableRawMode()
    if len(sys.argv) == 2:
        E.openFile(sys.argv[1])
    while True:
        E.refreshScreen()
        E.processKeyPress()


if __name__ == "__main__":
    main()
