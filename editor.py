import termios
import sys
from enum import Enum
import tty
import os
import time


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
        # -1 for the status bar and -1 for the status message
        self.screenrows = os.get_terminal_size().lines - 2
        self.screencols = os.get_terminal_size().columns
        self.buffer = ""
        self.renderX = 0  # Index into the rendered row
        self.cursorX = 0
        self.cursorY = 0
        self.EDITOR_VERSION = "0.0.1"
        self.rows = []
        self.renderedRows = []
        self.rowoffset = 0
        self.columnoffset = 0
        self.wordWrap = False
        self.filename = ""
        self.tabSize = 4
        self.dirty = False
        self.statusmsg = "HELP: Ctrl-Q to quit."
        self.statusmsgTime = time.time()

    # File I/O

    def openFile(self, filename):
        self.filename = filename
        file = open(filename, "r")
        for line in file.readlines():
            self.appendRow(line)

    def readKey(self):
        c = sys.stdin.read(1)
        if c == "\x1b":
            seq = []
            seq.append(sys.stdin.read(1))
            seq.append(sys.stdin.read(1))

            if seq[0] == "[":
                if seq[1] >= "0" and seq[1] <= "9":
                    seq.append(sys.stdin.read(1))
                    if seq[2] == "~":
                        match seq[1]:
                            case "1":
                                return Keys.HOME
                            case "3":
                                return Keys.DEL
                            case "4":
                                return Keys.END
                            case "5":
                                return Keys.PAGE_UP
                            case "6":
                                return Keys.PAGE_DOWN
                            case "7":
                                return Keys.HOME
                            case "8":
                                return Keys.END
                else:
                    match (seq[1]):
                        case "A":
                            return Keys.ARROW_UP
                        case "B":
                            return Keys.ARROW_DOWN
                        case "C":
                            return Keys.ARROW_RIGHT
                        case "D":
                            return Keys.ARROW_LEFT
                        case "H":
                            return Keys.HOME
                        case "F":
                            return Keys.END
            elif seq[0] == "O":
                match seq[1]:
                    case "H":
                        return Keys.HOME
                    case "F":
                        return Keys.END
            return "\x1b"
        else:
            return c

    def moveCursor(self, c):
        row = "" if self.cursorY >= len(self.rows) else self.rows[self.cursorY]
        match c:
            case Keys.ARROW_UP:
                if self.cursorY > 0:
                    self.cursorY -= 1
            case Keys.ARROW_LEFT:
                if self.cursorX > 0:
                    self.cursorX -= 1
                elif self.cursorY > 0:
                    self.cursorY -= 1
                    self.cursorX = len(self.rows[self.cursorY])
            case Keys.ARROW_DOWN:
                if self.cursorY < len(self.rows):
                    self.cursorY += 1
            case Keys.ARROW_RIGHT:
                if row != "" and self.cursorX < len(row):
                    self.cursorX += 1
                elif self.cursorX == len(row):
                    self.cursorX = 0
                    self.cursorY += 1

        row = "" if self.cursorY >= len(self.rows) else self.rows[self.cursorY]
        if self.cursorX > len(row):
            self.cursorX = len(row)

    def processKeyPress(self):
        c = self.readKey()
        self.dirty = True
        match c:
            case "\x11":  # CTRL-Q
                sys.stdout.write("\x1b[2J")
                sys.stdout.write("\x1b[H")
                self.disableRawMode()
                exit(0)
            case Keys.ARROW_UP | Keys.ARROW_DOWN | Keys.ARROW_LEFT | Keys.ARROW_RIGHT:
                self.moveCursor(c)
            case Keys.PAGE_UP:
                self.cursorY = self.rowoffset
                for i in range(self.screenrows):
                    self.moveCursor(Keys.ARROW_UP)
            case Keys.PAGE_DOWN:
                self.cursorY = self.rowoffset + self.screenrows - 1
                if self.cursorY > len(self.rows):
                    self.cursorY = len(self.rows)
                for i in range(self.screenrows):
                    self.moveCursor(Keys.ARROW_DOWN)
            case Keys.HOME:
                self.cursorX = 0
            case Keys.END:
                if self.cursorY < len(self.rows):
                    self.cursorX = len(self.rows[self.cursorY])
            case _:
                self.insertChar(c)

    # Row operations

    def rowCxToRx(self, string, cx):
        rx = 0
        for i in range(cx):
            if string[i] == "\t":
                rx += (self.tabSize - 1) - (rx % self.tabSize)
            rx += 1
        return rx

    def rowInsertChar(self, y, at, c):
        if at < 0 or at > len(self.rows[y]):
            at = len(self.rows[y])
        left = self.rows[y][:at]
        right = self.rows[y][at:]
        self.rows[y] = left + c + right
        self.updateRow(y)

    def updateRow(self, at):
        tabs = 0
        self.renderedRows[at] = ""
        for i in range(len(self.rows[at])):
            if self.rows[at][i] == "\t":
                self.renderedRows[at] += " " * self.tabSize
            else:
                self.renderedRows[at] += self.rows[at][i]

    def appendRow(self, string):
        if string != "":
            if string[-1] == "\n":
                string = string[:-1]
        self.rows.append(string)
        self.renderedRows.append("")
        self.updateRow(len(self.rows) - 1)

    def drawRows(self):
        for y in range(0, self.screenrows):
            filerow = y + self.rowoffset
            if filerow >= len(self.rows):
                if y == self.screenrows // 3 and self.filename == "":
                    welcome = f"Dyledit -- version {self.EDITOR_VERSION}"
                    padding = (self.screencols - len(welcome)) // 2
                    self.buffer += "~"
                    while padding > 0:
                        padding -= 1
                        self.buffer += " "
                    self.buffer += welcome

                elif y == self.screenrows // 3 + 1 and self.filename == "":
                    python = "Python Edition"
                    padding = (self.screencols - len(python)) // 2
                    self.buffer += "~"
                    while padding > 0:
                        padding -= 1
                        self.buffer += " "
                    self.buffer += python
                else:
                    self.buffer += "~"
            else:
                length = len(self.renderedRows[filerow]) - self.columnoffset
                if length < 0:
                    length = 0
                if length > self.screencols and self.wordWrap == False:
                    length = self.screencols
                self.buffer += self.renderedRows[filerow][
                    self.columnoffset: self.columnoffset + length
                ]

            self.buffer += "\x1b[K"
            self.buffer += "\r\n"

    def setStatusMessage(self, string):
        self.statusmsg = string
        self.statusmsgTime = time.time()

    def drawStatusBar(self):
        self.buffer += "\x1b[7m"
        status = f"{self.filename} - {len(self.rows)} lines"
        rstatus = f"{self.cursorY + 1}/{len(self.rows)}"
        self.buffer += status
        length = len(status)
        while length < self.screencols:
            if self.screencols - length == len(rstatus):
                self.buffer += rstatus
                break
            self.buffer += " "
            length += 1
        self.buffer += "\x1b[m"
        self.buffer += "\r\n"

    def drawMessageBar(self):
        self.buffer += "\x1b[K"
        msglen = len(self.statusmsg)
        if msglen > self.screencols:
            msglen = self.screencols
        if msglen > 0 and time.time() - self.statusmsgTime < 5:
            self.buffer += self.statusmsg

    def scroll(self):
        self.renderX = 0
        if self.cursorY < len(self.rows):
            self.renderX = self.rowCxToRx(
                self.rows[self.cursorY], self.cursorX)

        if self.cursorY < self.rowoffset:
            self.rowoffset = self.cursorY
        if self.cursorY >= self.rowoffset + self.screenrows:
            self.rowoffset = self.cursorY - self.screenrows + 1

        if self.renderX < self.columnoffset:
            self.columnoffset = self.renderX
        if self.renderX >= self.columnoffset + self.screencols:
            self.columnoffset = self.renderX - self.screencols + 1

    def insertChar(self, c):
        if (self.cursorY == len(self.rows)):
            self.appendRow("")
        self.rowInsertChar(self.cursorY, self.cursorX, c)
        self.cursorX += 1

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
        sys.stdout.write("\x1b[2J")
        sys.stdout.write("\x1b[H")
        self.disableRawMode()
        exit(0)

    def refreshScreen(self):
        self.scroll()

        self.buffer = ""
        self.buffer += "\x1b[?25l"  # Hide cursor before repainting

        self.buffer += "\x1b[H"
        self.drawRows()
        self.drawStatusBar()
        self.drawMessageBar()

        self.buffer += f"\x1b[{ self.cursorY - self.rowoffset + 1};{ self.renderX - self.columnoffset + 1}H"

        self.buffer += "\x1b[?25h"  # Show cursor again

        sys.stdout.write(self.buffer)
