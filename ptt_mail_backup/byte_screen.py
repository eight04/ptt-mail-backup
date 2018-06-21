"""
A pyte screen that is allowed to draw unprintable characters.
"""

from wcwidth import wcwidth
from .pyte.screens import Screen, mo, unicodedata

class ByteScreen(Screen):
    def draw(self, data):
        data = data.translate(
            self.g1_charset if self.charset else self.g0_charset)

        for char in data:
            char_width = wcwidth(char)

            # If this was the last column in a line and auto wrap mode is
            # enabled, move the cursor to the beginning of the next line,
            # otherwise replace characters already displayed with newly
            # entered.
            if self.cursor.x == self.columns:
                if mo.DECAWM in self.mode:
                    self.dirty.add(self.cursor.y)
                    self.carriage_return()
                    self.linefeed()
                elif char_width > 0:
                    self.cursor.x -= char_width

            # If Insert mode is set, new characters move old characters to
            # the right, otherwise terminal is in Replace mode and new
            # characters replace old characters at cursor position.
            if mo.IRM in self.mode and char_width > 0:
                self.insert_characters(char_width)

            line = self.buffer[self.cursor.y]
            if char_width == 1 or char_width < 0:
                char_width = 1
                line[self.cursor.x] = self.cursor.attrs._replace(data=char)
            elif char_width == 2:
                # A two-cell character has a stub slot after it.
                line[self.cursor.x] = self.cursor.attrs._replace(data=char)
                if self.cursor.x + 1 < self.columns:
                    line[self.cursor.x + 1] = self.cursor.attrs \
                        ._replace(data="")
            elif char_width == 0 and unicodedata.combining(char):
                # A zero-cell character is combined with the previous
                # character either on this or preceeding line.
                if self.cursor.x:
                    last = line[self.cursor.x - 1]
                    normalized = unicodedata.normalize("NFC", last.data + char)
                    line[self.cursor.x - 1] = last._replace(data=normalized)
                elif self.cursor.y:
                    last = self.buffer[self.cursor.y - 1][self.columns - 1]
                    normalized = unicodedata.normalize("NFC", last.data + char)
                    self.buffer[self.cursor.y - 1][self.columns - 1] = \
                        last._replace(data=normalized)
            else:
                break  # Unprintable character or doesn't advance the cursor.

            # .. note:: We can't use :meth:`cursor_forward()`, because that
            #           way, we'll never know when to linefeed.
            if char_width > 0:
                self.cursor.x = min(self.cursor.x + char_width, self.columns)

        self.dirty.add(self.cursor.y)
        