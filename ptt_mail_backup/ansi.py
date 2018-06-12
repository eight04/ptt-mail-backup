from collections import namedtuple
from pyte.graphics import FG_ANSI, BG_ANSI

fg2code = {name: str(key).encode("latin-1") for key, name in FG_ANSI.items()}
bg2code = {name: str(key).encode("latin-1") for key, name in BG_ANSI.items()}

RESET = b"\x1b[m"

ColorState = namedtuple("ColorState", ["bold", "blink", "fg", "bg"])

DEFAULT_COLOR = ColorState(False, False, "white", "black")

def char_to_color(char):
    fg = char.fg if char.fg != "default" else "white"
    bg = char.bg if char.bg != "default" else "black"
    if char.reverse:
        fg, bg = bg, fg
    return ColorState(char.bold, char.blink, fg, bg)        

def code_to_ansi(codes):
    return b"\x1b[" + b";".join(codes) + b"m"
    
def diff(color, other):
    """Rerturn an escape sequence that would transform color state from
    ``other`` to ``color``.
    """
    if color == DEFAULT_COLOR:
        return RESET # reset
    codes = []
    if (color.bold != other.bold and not color.bold or
            color.blink != other.blink and not color.blink):
        # reset
        codes.append(b"0")
        other = DEFAULT_COLOR
        
    if color.bold and color.bold != other.bold:
        codes.append(b"1")
    if color.blink and color.blink != other.blink:
        codes.append(b"5")
    if color.fg != other.fg:
        codes.append(fg2code[color.fg])
    if color.bg != other.bg:
        codes.append(bg2code[color.bg])
    return code_to_ansi(codes)
        
def colored_sequence(chars):
    color = DEFAULT_COLOR
    for c in chars:
        if c is None:
            yield b" "
            continue
        next_color = char_to_color(c)
        if color != next_color:
            yield diff(next_color, color)
            color = next_color
        yield c.data.encode("latin-1")
    if color != DEFAULT_COLOR:
        yield RESET
        
def chars_to_bytes(chars):
    """Convert a list of :class:`pyte.screens.Char` into ansi escape sequence.
    """
    return b"".join(colored_sequence(chars))
