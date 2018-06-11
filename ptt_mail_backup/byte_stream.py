"""
A pyte stream that would work with bytes.
"""
import re
import pyte

def no_c1_pattern(rx):
    # pyte uses a single backslash to escape every characters
    pattern = re.sub(r"\\[\x9b\x9d]", "", rx.pattern)
    return re.compile(pattern)
        
class ByteStream(pyte.ByteStream):
    # pylint: disable=protected-access
    # https://github.com/selectel/pyte/issues/118
    _text_pattern = no_c1_pattern(pyte.ByteStream._text_pattern)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.select_other_charset("@")
