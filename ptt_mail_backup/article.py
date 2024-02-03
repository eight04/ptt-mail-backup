import uao

from .ansi import chars_to_bytes

uao.register_uao()

def is_default(char):
    return not char.bold and char.fg == "default" and char.bg == "default"
    
def is_truncated(char):
    return char.bold and char.data in {"<", ">"}
    
class ArticleScreenLine:
    def __init__(self, line, line_no, col_start):
        skip_start = 0
        if is_truncated(line[0]):
            if line[1].data == "?":
                skip_start = 2
            else:
                skip_start = 1
                
        skip_end = 0
        if is_truncated(line[78]) and is_default(line[79]):
            if line[77].data == "?":
                skip_end = 3
            else:
                skip_end = 2
                
        self.line_no = line_no
        self.col_no = col_start + skip_start
        self.chars = line[skip_start:len(line) - skip_end]
        self.left_truncated = bool(skip_start)
        self.right_truncated = bool(skip_end)
        
class ArticleScreen:
    def __init__(self, lines, y, x):
        self.y = y
        self.x = x
        self.lines = [
            ArticleScreenLine(line, line_no, self.x)
            for line_no, line in enumerate(lines, self.y)
        ]
        
class Article:
    """Article composer. Compose multiple screens into an article."""
    def __init__(self, date, sender, title):
        self.date = date
        self.sender = sender
        self.title = title
        self.lines = []
        
    def draw_char(self, line_no, col_no, char):
        if col_no >= len(self.lines[line_no]):
            self.lines[line_no].extend([None] * (col_no - len(self.lines[line_no]) + 1))
                
        if self.lines[line_no][col_no] is None:
            self.lines[line_no][col_no] = char
        
    def draw_line(self, line):
        if line.line_no == len(self.lines) and line.col_no == 0:
            # no need to draw char but append the entire line
            self.lines.append(line.chars)
            return
            
        if line.line_no >= len(self.lines):
            for _i in range(line.line_no - len(self.lines) + 1):
                self.lines.append([])
            
        for col_no, char in enumerate(line.chars, line.col_no):
            self.draw_char(line.line_no, col_no, char)
        
    def add_screen(self, lines, y, x, skip_line=None):
        screen = ArticleScreen(lines, y, x)
        for line in screen.lines:
            if skip_line and skip_line(line):
                continue
            self.draw_line(line)
        return screen
        
    def to_bytes(self):
        return b"\r\n".join(chars_to_bytes(l).rstrip() for l in self.lines)
