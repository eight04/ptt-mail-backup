from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from contextlib import contextmanager
from getpass import getpass
import logging
import math
from pathlib import Path
# from pdb import set_trace
import re

# from PTTLibrary import PTT
from paramiko.client import SSHClient, AutoAddPolicy
# from ptt_article_parser import strip_color
import pyte
import pyte.graphics
from pyperclip import copy
from uao import register_uao

__version__ = "0.0.0"

register_uao()
logging.basicConfig(level="INFO")
log = logging.getLogger(__name__)

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
    foot_rx = re.compile(r"(?:(\d+)~(\d+)\s*欄.+?)?(\d+)~(\d+)\s*行".encode("big5-uao"))
    
    def __init__(self, lines):
        lines = list(lines)
        
        result = self.foot_rx.search(lines[-1]).groups()
        # make number zero-based
        col_start, col_end, line_start, line_end = [
            int(n) - 1 if n is not None else None for n in result
        ]
        if not col_start:
            col_start = 0
        if not col_end:
            col_end = 77
            
        self.line_start = line_start
        self.line_end = line_end
        self.col_start = col_start
        self.col_end = col_end
        
        self.lines = [
            ArticleScreenLine(line, line_no, col_start)
            for line_no, line in enumerate(lines[:-1], line_start)
        ]
        
def is_default(char):
    return not char.bold and char.fg == "default" and char.bg == "default"
    
def is_truncated(char):
    return char.bold and (char.data == "<" or char.data == ">")
        
class Article:
    """Article composer. Compose multiple screens into an article."""
    def __init__(self):
        self.lines = []
        
    def draw_char(self, line_no, col_no, char):
        if col_no >= len(self.lines[line_no]):
            self.lines[line_no].extend([None] * (line_no - len(self.lines[line_no]) + 1))
                
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
            
        for col_no, char in enumerate(line.col_no, line.chars):
            self.draw_char(line.line_no, col_no, char)
        
    def add_screen(self, lines):
        screen = ArticleScreen(lines)
        assert screen.line_start <= len(self.lines)
        for line in screen.lines:
            self.draw_line(line)
        return screen
        
    def to_bytes(self):
        return b"\r\n".join(b"".join(colored_sequence(l)).rstrip() for l in self.lines)
        
def is_no(text):
    return bool(re.match(r"\s*(n|no)\s*", text, re.I))
    
def no_c1_pattern(rx):
    # pyte uses a single backslash to escape every characters
    pattern = re.sub(r"\\[\x9b\x9d]", "", rx.pattern)
    return re.compile(pattern)
        
class PTTBot:
    def __init__(self, user=None, password=None):
        self.client = SSHClient()
        self.client.set_missing_host_key_policy(AutoAddPolicy)
        self.channel = None
        self.user = user
        self.password = password
        self.screen = pyte.Screen(80, 24)
        self.stream = pyte.ByteStream(self.screen)
        self.stream.select_other_charset("@")
        # pylint: disable=protected-access
        # https://github.com/selectel/pyte/issues/118
        self.stream._text_pattern = no_c1_pattern(pyte.ByteStream._text_pattern)
        self.article_configured = False
        
    def __enter__(self, *args):
        if not self.user:
            self.user = input("User: ")
        if not self.password:
            self.password = getpass()
        self.client.connect("ptt.cc", username="bbs", password="")
        self.channel = self.client.invoke_shell()
        self.channel.settimeout(10)
        
        self.channel.recv(math.inf)
        
        self.unt("請輸入代號")
        log.info("start login")
        self.send(self.user + "\r" + self.password + "\r")
        self.unt("任意鍵", on_data=self.handle_login)
        log.info("%s login success", self.user)
        self.send("qqq")
        # set_trace()
        self.unt("主功能表")
        log.info("enter main menu")
        return self
        
    def handle_login(self, data):
        if "刪除其他重複登入".encode("big5-uao") in data:
            if is_no(input("Kick multiple account? [Y/n] ")):
                self.send("n\r")
            else:
                log.info("kicked another account")
                self.send("\r")
        if "編輯器自動復原".encode("big5-uao") in data:
            result = input("Save unsaved article? [0-9/n] ")
            if is_no(result) or result == "":
                self.send("q\r")
            else:
                self.send("s\r{}\r".format(int(result)))
        
    def __exit__(self, *args):
        self.client.close()
    
    def unt(self, needle, on_data=None):
        if callable(needle):
            should_stop = needle
        else:
            def should_stop(data, test=needle.encode("big5-uao")):
                return test in data
                
        while True:
            data = self.channel.recv(math.inf)
            if on_data:
                on_data(data)
            self.stream.feed(data)
            if should_stop(data):
                return
        
    def send(self, data):
        pos = 0
        while True:
            sent = self.channel.send(data[pos:])
            pos += sent
            if pos >= len(data):
                return
        
    @contextmanager
    def enter_mail(self):
        self.send(b"\x1am")
        self.unt("郵件選單")
        log.info("get in the mail box")
        yield
        self.send("q")
        self.unt("主功能表")
        log.info("get out the mail box")
        
    def get_last_index(self):
        log.info("get last index")
        # set_trace()
        self.send("$h")
        last_index = None
        def on_data(data):
            nonlocal last_index
            if "呼叫小天使".encode("big5-uao") not in data:
                return
            for line in self.lines(reverse=True):
                # set_trace()
                line = line.decode("big5-uao")
                # print(line)
                match = re.search(r"^●?\s*(\d+)", line)
                if match:
                    last_index = int(match.group(1))
                    break
        self.unt("呼叫小天使", on_data=on_data)
        self.send("q")
        log.info("get last index success: %s", last_index)
        return last_index
        
    def lines(self, reverse=False, color=False, raw=False):
        if reverse:
            it = range(self.screen.lines - 1, -1, -1)
        else:
            it = range(self.screen.lines)
        for i in it:
            if raw:
                yield self.get_raw_line(i)
            else:
                yield self.get_line(i, color=color)
                
    def get_raw_line(self, line_no):
        if line_no < 0:
            line_no += self.screen.lines
        return [self.screen.buffer[line_no][i] for i in range(self.screen.columns)]
                    
    def get_line(self, line_no, color=False):
        chars = self.get_raw_line(line_no)
        if not color:
            return "".join(c.data for c in chars).encode("latin-1")
        return b"".join(colored_sequence(chars))
        
    def update_article_config(self):
        """Update article config. It is hard to work with articles containing
        long lines (column > 80).
        """
        self.article_configured = True
        self.send("owml ")
        rx = re.compile(r"\s*瀏覽\s*第\s*\d+/\d+\s*頁".encode("big5-uao"))
        def is_article(_data):
            last_line = self.get_line(self.screen.lines - 1)
            return rx.match(last_line)
        self.unt(is_article)
        
    first_col_needle = "目前顯示:".encode("big5-uao")
    def on_first_col(self, _data):
        return self.first_col_needle in self.get_line(-1)
        
    def on_col(self, col_no):
        needle = "{}~{} 欄".format(col_no + 1, col_no + 78)
        def callback(_data):
            return needle in self.get_line(-1)
        return callback
        
    def get_article(self, index):
        log.info("get %sth article", index)
        self.send(str(index) + "\r\r")
        
        is_animated = False
        def handle_animated(data):
            nonlocal is_animated
            if "這份文件是可播放的文字動畫".encode("big5-uao") in data:
                log.info("skip animation")
                self.send("n")
                is_animated = True
        self.unt(self.on_first_col, on_data=handle_animated)
        
        if is_animated:
            self.send("hq")
            self.unt(self.on_first_col)
            log.info("refresh animation page")
            
        if not self.article_configured:
            self.update_article_config()
            
        log.info("start collecting body")
        
        article = Article()
        # rx_last_page = re.compile(r"瀏覽.+?\(100%\)".encode("big5-uao"))
        while True:
            screen = article.add_screen(self.lines(raw=True))
            log.info("add screen %s~%s", screen.line_start, screen.line_end)
            
            indent = 0
            while any(line.right_truncated for line in screen.lines):
                indent += 1
                self.send(">")
                self.unt(self.on_col(screen.col_start + 8))
                screen = article.add_screen(self.lines(raw=True))
                log.info("move right to col %s", screen.col_start)
                
            if indent:
                self.send("<" * indent)
                self.unt(self.on_first_col)
            
            if self.on_last_page():
                break
                
            self.send(" ")
            self.unt(lambda _data: self.on_last_page() or self.on_line(screen.line_end))
        self.send("q")
        
        log.info("get article success")
        return article.to_bytes()
        
    rx_last_page = re.compile(r"瀏覽.+?\(100%\)".encode("big5-uao"))
    def on_last_page(self):
        return self.rx_last_page.search(self.get_line(-1))
        
    def on_line(self, line_no):
        needle = "{}~{} 行".format(line_no + 1, line_no + len(self.screen.lines) - 1)
        needle = needle.encode("big5-uao")
        return needle in self.get_line(-1)
        
def main():
    parser = ArgumentParser(description="Backup PTT mail.")
    parser.add_argument(
        "--user", help="username, otherwise prompt for the value."
    )
    parser.add_argument(
        "--pass", dest="password", help="password, otherwise prompt for the value."
    )
    parser.add_argument(
        "--dest", default=".", help="save to dest. Default to current dir."
    )
    range_group = parser.add_mutually_exclusive_group(required=True)
    range_group.add_argument(
        "--range", nargs=2, type=int, metavar=("START", "END"),
        help="specify a range (inclusive). Negative values and zeros are "
             "allowed, they are treated as (last_index + value) i.e. --range 0 "
             "0 would download the last mail."
    )
    range_group.add_argument("--all", action="store_true", help="download all")
    args = parser.parse_args()
    
    with PTTBot(args.user, args.password) as bot:
        with bot.enter_mail():
            last_index = bot.get_last_index()
            if args.range:
                start, end = args.range
                if start <= 0:
                    start += last_index
                if end <= 0:
                    end += last_index
            elif args.all:
                start = 1
                end = last_index
            else:
                raise TypeError("invalid range")
                
            for i in range(start, end + 1):
                content = bot.get_article(i)
                file = Path("ptt_mail_backup_{}.ans".format(i))
                file.write_bytes(content)
   