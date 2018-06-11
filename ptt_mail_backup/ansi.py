import pyte.graphics

fg2code = {name: str(key).encode("latin-1") for key, name in pyte.graphics.FG_ANSI.items()}
bg2code = {name: str(key).encode("latin-1") for key, name in pyte.graphics.BG_ANSI.items()}

fg2code.update({"default": b"37"})
bg2code.update({"default": b"40"})

def code_to_ansi(codes):
    return b"\x1b[" + b";".join(codes) + b"m"

class ColorState:
    RESET = b"\x1b[m"
    
    def __init__(self, init=None):
        self.bold = False
        self.fg = "default"
        self.bg = "default"
        
        if init:
            self.bold = init.bold
            self.fg = init.fg
            self.bg = init.bg
            
    def __eq__(self, other):
        return (
            self.bold == other.bold and
            self.fg == other.fg and
            self.bg == other.bg
        )
    
    def is_default(self):
        return not self.bold and self.fg == "default" and self.bg == "default"
        
    def diff(self, other):
        if self.is_default():
            return ColorState.RESET # reset
        codes = []
        if self.bold != other.bold:
            if not self.bold: # remove bold
                codes.append(b"0")
                codes.append(fg2code[self.fg])
                codes.append(bg2code[self.bg])
                return code_to_ansi(codes)
            codes.append(b"1")
        if self.fg != other.fg:
            codes.append(fg2code[self.fg])
        if self.bg != other.bg:
            codes.append(bg2code[self.bg])
        return code_to_ansi(codes)
            
    def gen(self, bg=None, fg=None, bold=None):
        if bg is None:
            bg = self.bg
        if fg is None:
            fg = self.fg
        if bold is None:
            bold = self.bold
        return self.bg

def colored_sequence(chars):
    color = ColorState()
    for c in chars:
        if c is None:
            yield b" "
            continue
        next_color = ColorState(c)
        if color != next_color:
            yield next_color.diff(color)
            color = next_color
        yield c.data.encode("latin-1")
    if not color.is_default():
        yield ColorState.RESET
        
def chars_to_bytes(chars):
    return b"".join(colored_sequence(chars))
