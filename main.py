import tty
import sys
import termios
import os
from enum import Enum

DYLEDIT_VERSION = "0.0.1"


class Keys(Enum):
    ARROW_UP = 1000
    ARROW_DOWN = 1001
    ARROW_LEFT = 1002
    ARROW_RIGHT = 1003
    PAGE_UP = 1004
    PAGE_DOWN = 1005
    HOME = 1006
    END = 1007
    DEL = 1008


class EditorConfig:
    def __init__(self):
        self.orig_termios = termios.tcgetattr(sys.stdin)
        self.screenrows = os.get_terminal_size().lines
        self.screencols = os.get_terminal_size().columns
        self.buffer = ""
        self.cursorX = 0
        self.cursorY = 0


E = EditorConfig()


def enableRawMode():
    tty.setraw(sys.stdin)
    temp = termios.tcgetattr(sys.stdin)
    temp[0] &= ~(termios.ICRNL)
    temp[1] &= ~(termios.OPOST)
    termios.tcsetattr(sys.stdin, termios.TCSANOW, temp)


def disableRawMode():
    termios.tcsetattr(sys.stdin, termios.TCSANOW, E.orig_termios)


def die():
    sys.stdout.write('\x1b[2J')
    sys.stdout.write('\x1b[H')
    disableRawMode()
    exit(0)


def readKey():
    c = sys.stdin.read(1)
    if (c == '\x1b'):
        seq = []
        seq.append(sys.stdin.read(1))
        seq.append(sys.stdin.read(1))

        if seq[0] == '[':
            if seq[1] >= '0' and seq[1] <= '9':
                seq.append(sys.stdin.read(1))
                if seq[2] == '~':
                    match seq[1]:
                        case '1': return Keys.HOME
                        case '3': return Keys.DEL
                        case '4': return Keys.END
                        case '5': return Keys.PAGE_UP
                        case '6': return Keys.PAGE_DOWN
                        case '7': return Keys.HOME
                        case '8': return Keys.END
            else:
                match(seq[1]):
                    case 'A': return Keys.ARROW_UP
                    case 'B': return Keys.ARROW_DOWN
                    case 'C': return Keys.ARROW_RIGHT
                    case 'D': return Keys.ARROW_LEFT
                    case 'H': return Keys.HOME
                    case 'F': return Keys.END
        elif seq[0] == 'O':
            match seq[1]:
                case 'H': return Keys.HOME
                case 'F': return Keys.END
        return '\x1b'
    else:
        return c


def moveCursor(c):
    match c:
        case Keys.ARROW_UP:
            if E.cursorY > 0:
                E.cursorY -= 1
        case Keys.ARROW_LEFT:
            if E.cursorX > 0:
                E.cursorX -= 1
        case Keys.ARROW_DOWN:
            if E.cursorY < E.screenrows:
                E.cursorY += 1
        case Keys.ARROW_RIGHT:
            if E.cursorX < E.screencols:
                E.cursorX += 1


def processKeyPress():
    c = readKey()
    match c:
        case '\x11':  # CTRL-Q
            sys.stdout.write('\x1b[2J')
            sys.stdout.write('\x1b[H')
            disableRawMode()
            exit(0)
        case Keys.ARROW_UP | Keys.ARROW_DOWN | Keys.ARROW_LEFT | Keys.ARROW_RIGHT:
            moveCursor(c)
        case Keys.PAGE_UP:
            for i in range(E.screenrows):
                moveCursor(Keys.ARROW_UP)
        case Keys.PAGE_DOWN:
            for i in range(E.screenrows):
                moveCursor(Keys.ARROW_DOWN)
        case Keys.HOME:
            E.cursorX = 0
        case Keys.END:
            E.cursorX = E.screencols - 1


def editorDrawRows():
    for y in range(0, E.screenrows):

        if y == E.screenrows // 3:
            welcome = f"Dyledit -- version {DYLEDIT_VERSION}"
            padding = (E.screencols - len(welcome)) // 2
            E.buffer += "~"
            while (padding > 0):
                padding -= 1
                E.buffer += " "
            E.buffer += welcome

        elif y == E.screenrows // 3 + 1:
            python = "Python Edition"
            padding = (E.screencols - len(python)) // 2
            E.buffer += "~"
            while (padding > 0):
                padding -= 1
                E.buffer += " "
            E.buffer += python

        else:
            E.buffer += "~"
        E.buffer += "\x1b[K"
        if y < E.screenrows - 1:
            E.buffer += "\r\n"


def refreshScreen():
    E.buffer = ""
    E.screencols = os.get_terminal_size().columns
    E.screenrows = os.get_terminal_size().lines

    E.buffer += "\x1b[?25l"  # Hide cursor before repainting

    E.buffer += '\x1b[H'
    editorDrawRows()

    # Move cursor back to 0,0
    E.buffer += f"\x1b[{E.cursorY + 1};{E.cursorX + 1}H"

    E.buffer += '\x1b[?25h'  # Show cursor again

    sys.stdout.write(E.buffer)


def main():
    enableRawMode()
    while True:
        refreshScreen()
        processKeyPress()


if __name__ == "__main__":
    main()
