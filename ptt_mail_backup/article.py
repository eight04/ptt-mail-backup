import re
import collections

from .ansi import chars_to_bytes

RX_FOOT = re.compile(r"(?:(\d+)~(\d+)\s*欄.+?)?(\d+)~(\d+)\s*行".encode("big5-uao"))

def is_default(char):
    return not char.bold and char.fg == "default" and char.bg == "default"
    
def is_truncated(char):
    return char.bold and (char.data == "<" or char.data == ">")
    
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
        
Foot = collections.namedtuple("Foot", ["col_start", "col_end", "line_start", "line_end"])
        
def match_foot(s):
    match = RX_FOOT.search(s)
    if not match:
        return None
    col_start, col_end, line_start, line_end = match.groups()
    
    col_start = int(col_start) - 2 if col_start is not None else 0
    col_end = int(col_end) if col_end is not None else 78
    line_start = int(line_start) - 1
    line_end = int(line_end)
    return Foot(col_start, col_end, line_start, line_end)
        
class ArticleScreen:
    def __init__(self, lines):
        lines = list(lines)
        foot = match_foot("".join(c.data for c in lines[-1]).encode("latin-1"))
        
        self.line_start = foot.line_start
        self.line_end = foot.line_end
        self.col_start = foot.col_start
        self.col_end = foot.col_end
        
        self.lines = [
            ArticleScreenLine(line, line_no, self.col_start)
            for line_no, line in enumerate(lines[:-1], self.line_start)
        ]
        
class Article:
    """Article composer. Compose multiple screens into an article."""
    def __init__(self):
        self.lines = []
        
    def draw_char(self, line_no, col_no, char):
        if col_no >= len(self.lines[line_no]):
            self.lines[line_no].extend([None] * (col_no - len(self.lines[line_no]) + 1))
                
        if self.lines[line_no][col_no] is None:
            self.lines[line_no][col_no] = char
        
    def draw_line(self, line):
        if line.line_no > len(self.lines):
            for _i in range(line.line_no - len(self.lines)):
                self.lines.append([])
                
        if line.line_no == len(self.lines) and line.col_no == 0:
            # no need to draw char
            self.lines.append(line.chars)
            return
            
        for col_no, char in enumerate(line.chars, line.col_no):
            self.draw_char(line.line_no, col_no, char)
        
    def add_screen(self, lines, skip_line=None):
        screen = ArticleScreen(lines)
        assert screen.line_start <= len(self.lines)
        for line in screen.lines:
            if skip_line and skip_line(line):
                continue
            self.draw_line(line)
        return screen
        
    def to_bytes(self):
        return b"\r\n".join(chars_to_bytes(l).rstrip() for l in self.lines)
