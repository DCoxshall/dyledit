import termios
import sys
from enum import Enum
import tty
import os
import time
import select


class Keys(Enum):
    BACKSPACE = 127
    ARROW_UP = 1000
    ARROW_DOWN = 1001
    ARROW_LEFT = 1002
    ARROW_RIGHT = 1003
    PAGE_UP = 1004
    PAGE_DOWN = 1005
    HOME = 1006
    END = 1007
    DEL = 1008
    ESCAPE = 1009


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
        self.statusmsg = "HELP: Ctrl-Q to quit, CTRL-S to save"
        self.statusmsgTime = time.time()
        self.quitTimes = 3

        # Used for searching
        self.search_last_match = -1
        self.search_direction = 1

    # File I/O

    def openFile(self, filename):
        self.filename = filename
        file = open(filename, "r")
        for line in file.readlines():
            self.insertRow(len(self.rows), line)
        file.close()

    def rowsToString(self):
        string = ""
        for row in self.rows:
            string += row + "\n"
        return string

    def editorSave(self):
        if self.filename == "":
            self.filename = self.editorPrompt(
                "Save as: %s (ESC to cancel)", None)

        if self.filename == "":
            self.setStatusMessage("Save aborted")
            return
        file = open(self.filename, "w+")
        string = self.rowsToString()
        file.write(string)
        file.close()
        self.dirty = False
        self.setStatusMessage(f"{len(string)} bytes written to disk")

    # find

    def editorFind(self):
        saved_cursorX = self.cursorX
        saved_cursorY = self.cursorY
        saved_columnoffset = self.columnoffset
        saved_rowoffset = self.rowoffset

        query = self.editorPrompt(
            "Search: %s (ESC/Arrows/Enter)", self.editorFindCallback)
        if query == "":
            self.cursorX = saved_cursorX
            self.cursorY = saved_cursorY
            self.columnoffset = saved_columnoffset
            self.rowoffset = saved_rowoffset

    def editorFindCallback(self, query, key):
        if key == '\r' or key == '\x1b':
            self.search_last_match = -1
            self.search_direction = 1
            return
        elif key == Keys.ARROW_RIGHT or key == Keys.ARROW_DOWN:
            self.search_direction = 1
        elif key == Keys.ARROW_LEFT or key == Keys.ARROW_UP:
            self.search_direction = -1
        else:
            self.search_last_match = -1
            self.search_direction = 1

        if self.search_last_match == -1:
            self.search_direction = 1

        finish = self.search_last_match - 1  # Used to prevent infinite searching
        if finish < 0:
            finish = len(self.rows) - 1

        current = self.search_last_match
        while current < len(self.rows) and current != finish:
            current += self.search_direction
            if current == -1:
                current = len(self.rows) - 1
            elif current == len(self.rows):
                current = 0

            if query in self.rows[current]:
                self.search_last_match = current
                self.cursorY = current
                self.cursorX = self.rowRxToCx(
                    self.rows[current], self.rows[current].index(query))
                self.rowoff = len(self.rows)
                break

    def readKey(self):
        p = select.poll()

        p.register(sys.stdin)
        x = p.poll(1)

        c = ""

        if x == [(0, 4)]: # There's no data to read
            return ""
        else: # There is data to read
            c = sys.stdin.read(1)

        if c == "\u007f":
            return Keys.BACKSPACE

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
                elif self.cursorX == len(row) and self.cursorY < len(self.rows):
                    self.cursorX = 0
                    self.cursorY += 1

        row = "" if self.cursorY >= len(self.rows) else self.rows[self.cursorY]
        if self.cursorX > len(row):
            self.cursorX = len(row)

    def processKeyPress(self):
        c = self.readKey()
        match c:
            case "":
                return
            case "\x11":  # CTRL-Q
                if self.dirty and self.quitTimes > 0:
                    self.setStatusMessage(
                        f"Warning: file has unsaved changes. Press Ctrl-Q {self.quitTimes} more times to quit")
                    self.quitTimes -= 1
                    return
                sys.stdout.write("\x1b[2J")
                sys.stdout.write("\x1b[H")
                self.disableRawMode()
                exit(0)
            case '\r':
                self.insertNewLine()
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
            case '\x06':  # CTRL-F = '\x06'
                self.editorFind()

            # TODO
            case Keys.BACKSPACE | '\x08':  # CTRL-H
                self.delChar()
            case Keys.DEL:
                if not self.cursorY == len(self.rows) - 1 or not self.cursorX == len(self.rows[len(self.rows) - 1]):
                    self.moveCursor(Keys.ARROW_RIGHT)
                self.delChar()

            # Handle CTRL-L and Escape by not doing anything
            case '\x0C':  # CTRL-L
                pass
            case '\x1b':
                pass

            case '\x13':  # CTRL-S
                self.editorSave()

            case _:
                self.insertChar(c)
                self.quitTimes = 3

    # Row operations

    def rowCxToRx(self, string, cx):
        rx = 0
        for i in range(cx):
            if string[i] == "\t":
                rx += (self.tabSize - 1) - (rx % self.tabSize)
            rx += 1
        return rx

    def rowRxToCx(self, row, rx):
        cur_rx = 0
        cx = 0
        while cx < len(row):
            if row[cx] == '\t':
                cur_rx += (self.tabSize - 1) - (cur_rx % self.tabSize)
            cur_rx += 1
            if cur_rx > rx:
                return cx
            cx += 1
        return cx

    def rowInsertChar(self, y, at, c):
        if at < 0 or at > len(self.rows[y]):
            at = len(self.rows[y])
        left = self.rows[y][:at]
        right = self.rows[y][at:]
        self.rows[y] = left + c + right
        self.updateRow(y)
        self.dirty = True

    def rowAppendString(self, at, string):
        self.rows[at] += string
        self.updateRow(at)
        self.dirty = True

    def rowDelChar(self, y, at):
        if at < 0 or at >= len(self.rows[y]):
            return
        left = self.rows[y][:at]
        right = self.rows[y][at:]
        if len(right) > 0:
            right = right[1:]
        self.rows[y] = left + right
        self.updateRow(y)
        self.dirty = True

    def updateRow(self, at):
        tabs = 0
        self.renderedRows[at] = ""
        for i in range(len(self.rows[at])):
            if self.rows[at][i] == "\t":
                self.renderedRows[at] += " " * self.tabSize
            else:
                self.renderedRows[at] += self.rows[at][i]

    def insertRow(self, at, string):
        if string != "":
            if string[-1] == "\n":
                string = string[:-1]
        self.rows.insert(at, string)
        self.renderedRows.insert(at, "")
        for i in range(at, len(self.rows)):
            self.updateRow(i)

    def delRow(self, at):
        if at < 0 or at >= len(self.rows):
            return
        del self.rows[at]
        for i in range(at, len(self.rows)):
            self.updateRow(i)
        self.dirty = True

    def drawRows(self):
        for y in range(0, self.screenrows):
            filerow = y + self.rowoffset
            if filerow >= len(self.rows):
                if y == self.screenrows // 3 and self.filename == "" and not self.dirty:
                    welcome = f"Dyledit -- version {self.EDITOR_VERSION}"
                    padding = (self.screencols - len(welcome)) // 2
                    self.buffer += "~"
                    while padding > 0:
                        padding -= 1
                        self.buffer += " "
                    self.buffer += welcome

                elif y == self.screenrows // 3 + 1 and self.filename == "" and not self.dirty:
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

    def setStatusMessage(self, string, *args):
        string = string % args
        self.statusmsg = string
        self.statusmsgTime = time.time()

    def drawStatusBar(self):
        self.buffer += "\x1b[7m"
        status = f"{self.filename} - {len(self.rows)} lines"
        if self.dirty == True:
            status += " - modified"
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
            self.insertRow(self.cursorY, "")
        self.rowInsertChar(self.cursorY, self.cursorX, c)
        self.cursorX += 1
        self.dirty = True

    def insertNewLine(self):
        if self.cursorX == 0:
            self.insertRow(self.cursorY, "")
        else:
            self.insertRow(self.cursorY + 1,
                           self.rows[self.cursorY][self.cursorX:])
            self.rows[self.cursorY] = self.rows[self.cursorY][:self.cursorX]
            self.updateRow(self.cursorY)
        self.cursorY += 1
        self.cursorX = 0

    def delChar(self):
        if self.cursorY == len(self.rows):
            return
        if self.cursorX == 0 and self.cursorY == 0:
            return

        if self.cursorX > 0:
            self.rowDelChar(self.cursorY, self.cursorX - 1)
            self.cursorX -= 1
        else:
            self.cursorX = len(self.rows[self.cursorY - 1])
            self.rowAppendString(self.cursorY - 1, self.rows[self.cursorY])
            self.delRow(self.cursorY)
            self.cursorY -= 1

    def editorPrompt(self, prompt, callback):
        userInput = ""

        while True:
            self.setStatusMessage(prompt, userInput)
            self.refreshScreen()

            c = self.readKey()
            if c == "":
                continue
            if c == Keys.DEL or c == '\x08' or c == Keys.BACKSPACE:
                userInput = userInput[:-1]
            elif c == '\x1b':
                self.setStatusMessage("")
                if callback != None:
                    callback(userInput, c)
                return ""
            elif c == '\r':
                if len(userInput) > 0:
                    self.setStatusMessage("")
                    if callback != None:
                        callback(userInput, c)
                    return userInput
            elif c == Keys.ARROW_DOWN or c == Keys.ARROW_LEFT or c == Keys.ARROW_RIGHT or c == Keys.ARROW_UP:
                pass
            elif ord(c) >= 32 and ord(c) <= 126:
                userInput += c

            if callback != None:
                callback(userInput, c)

    # Terminal Operations

    def enableRawMode(self):
        tty.setraw(sys.stdin)
        temp = termios.tcgetattr(sys.stdin)
        temp[0] &= ~(termios.ICRNL)
        temp[1] &= ~(termios.OPOST)
        termios.tcsetattr(sys.stdin, termios.TCSANOW, temp)

    def disableRawMode(self):
        termios.tcsetattr(sys.stdin, termios.TCSANOW, self.orig_termios)

    def die(self, errString):
        sys.stdout.write("\x1b[2J")
        sys.stdout.write("\x1b[H")
        print(errString)
        self.disableRawMode()
        exit(0)

    def refreshScreen(self):
        self.screencols = os.get_terminal_size().columns
        self.screenrows = os.get_terminal_size().lines - 2

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
