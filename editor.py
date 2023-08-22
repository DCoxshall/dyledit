import termios
import sys
from enum import Enum
import tty

import os


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


class Editor:
    def __init__(self):
        self.orig_termios = termios.tcgetattr(sys.stdin)
        self.screenrows = os.get_terminal_size().lines
        self.screencols = os.get_terminal_size().columns
        self.buffer = ""
        self.cursorX = 0
        self.cursorY = 0
        self.EDITOR_VERSION = "0.0.1"

    def readKey(self):
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

    def moveCursor(self, c):
        match c:
            case Keys.ARROW_UP:
                if self.cursorY > 0:
                    self.cursorY -= 1
            case Keys.ARROW_LEFT:
                if self.cursorX > 0:
                    self.cursorX -= 1
            case Keys.ARROW_DOWN:
                if self.cursorY < self.screenrows:
                    self.cursorY += 1
            case Keys.ARROW_RIGHT:
                if self.cursorX < self.screencols:
                    self.cursorX += 1

    def processKeyPress(self):
        c = self.readKey()
        match c:
            case '\x11':  # CTRL-Q
                sys.stdout.write('\x1b[2J')
                sys.stdout.write('\x1b[H')
                self.disableRawMode()
                exit(0)
            case Keys.ARROW_UP | Keys.ARROW_DOWN | Keys.ARROW_LEFT | Keys.ARROW_RIGHT:
                self.moveCursor(c)
            case Keys.PAGE_UP:
                for i in range(self.screenrows):
                    self.moveCursor(Keys.ARROW_UP)
            case Keys.PAGE_DOWN:
                for i in range(self.screenrows):
                    self.moveCursor(Keys.ARROW_DOWN)
            case Keys.HOME:
                self.cursorX = 0
            case Keys.END:
                self.cursorX = self.screencols - 1

    def drawRows(self):
        for y in range(0, self.screenrows):

            if y == self.screenrows // 3:
                welcome = f"Dyledit -- version {self.EDITOR_VERSION}"
                padding = (self.screencols - len(welcome)) // 2
                self.buffer += "~"
                while (padding > 0):
                    padding -= 1
                    self.buffer += " "
                self.buffer += welcome

            elif y == self.screenrows // 3 + 1:
                python = "Python Edition"
                padding = (self.screencols - len(python)) // 2
                self.buffer += "~"
                while (padding > 0):
                    padding -= 1
                    self.buffer += " "
                self.buffer += python

            else:
                self.buffer += "~"
            self.buffer += "\x1b[K"
            if y < self.screenrows - 1:
                self.buffer += "\r\n"

    # Terminal Operations

    def enableRawMode(self):
        tty.setraw(sys.stdin)
        temp = termios.tcgetattr(sys.stdin)
        temp[0] &= ~(termios.ICRNL)
        temp[1] &= ~(termios.OPOST)
        termios.tcsetattr(sys.stdin, termios.TCSANOW, temp)

    def disableRawMode(self):
        termios.tcsetattr(sys.stdin, termios.TCSANOW, self.orig_termios)

    def die(self):
        sys.stdout.write('\x1b[2J')
        sys.stdout.write('\x1b[H')
        self.disableRawMode()
        exit(0)

    def refreshScreen(self):
        self.buffer = ""
        self.screencols = os.get_terminal_size().columns
        self.screenrows = os.get_terminal_size().lines
        self.buffer += "\x1b[?25l"  # Hide cursor before repainting

        self.buffer += '\x1b[H'
        self.drawRows()

        # Move cursor back to 0,0
        self.buffer += f"\x1b[{ self.cursorY + 1};{ self.cursorX + 1}H"

        self.buffer += '\x1b[?25h'  # Show cursor again

        sys.stdout.write(self.buffer)
