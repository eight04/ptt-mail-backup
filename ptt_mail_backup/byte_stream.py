"""
A pyte stream that would work with bytes.
"""
import re
from .pyte import ByteStream as _ByteStream

def no_c1_pattern(rx):
    # pyte uses a single backslash to escape every characters
    # https://github.com/eight04/ptt-mail-backup/issues/7
    pattern = re.sub(r"\\[\x9b\x9d]|[\x9b\x9d]", "", rx.pattern)
    return re.compile(pattern)
        
class ByteStream(_ByteStream):
    # pylint: disable=protected-access
    # https://github.com/selectel/pyte/issues/118
    _text_pattern = no_c1_pattern(_ByteStream._text_pattern)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.select_other_charset("@")
