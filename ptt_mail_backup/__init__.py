from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from contextlib import contextmanager
from getpass import getpass
import logging
import math
from pathlib import Path
from pdb import set_trace
from pyperclip import copy
import re

# from PTTLibrary import PTT
from paramiko.client import SSHClient, AutoAddPolicy
# from ptt_article_parser import strip_color
from uao import register_uao
import pyte
import pyte.graphics

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
        
class Article:
    """Article composer. Compose multiple screens into an article."""
    foot_rx = re.compile(r"(?:(\d+)~(\d+)\s*欄.+?)?(\d+)~(\d+)\s*行".encode("big5-uao"))
    
    def __init__(self):
        self.lines = []
        
    def draw_char(self, line_no, col_no, char):
        if col_no >= len(self.lines[line_no]):
            for i in range(line_no - len(self.lines[line_no]) + 1):
                self.lines[line_no].append(None)
                
        if self.lines[line_no][col_no] is None:
            self.lines[line_no][col_no] = char
        
    def draw_line(line_no, col_start, line):
        if line_no > len(self.lines):
            for i in range(line_no - len(self.lines)):
                self.lines.append([])
            
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
                
        if line_no == len(self.lines) and col_start == 0:
            # no need to draw char
            self.lines.append(line)
            return
            
        col_start += skip_start
        line = line[skip_start:len(line) - skip_end]
        for col_no, char in enumerate(col_start, line):
            self.draw_char(line_no, col_no, char)
        
    def add_screen(self, lines):
        lines = list(lines)
        # set_trace()
        result = self.foot_rx.search(lines[-1]).groups()
        # make number zero-based
        col_start, col_end, line_start, line_end = [
            int(n) - 1 for n in result if n is not None else None
        ]
        if not col_start:
            col_start = 0
        if not col_end:
            col_end = 77
            
        assert line_start <= len(self.lines)
        for line_no, line in enumerate(lines[:-1], line_start):
            self.draw_line(line_no, col_start, line)
            
        return col_start, col_end, line_start, line_end
        
    def to_bytes(self):
        return b"\r\n".join(b"".join(colored_sequence(l)).rstrip() for l in self.lines)
        
def is_no(text):
    return bool(re.match("\s*(n|no)\s*", text, re.I))
    
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
        log.info("login success".format(self.user))
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
        if not callable(needle):
            def needle(data, test=needle.encode("big5-uao")):
                return test in data 
                
        while True:
            data = self.channel.recv(math.inf)
            if on_data:
                on_data(data)
            self.stream.feed(data)
            if needle(data):
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
        log.info("get last index success: {}".format(last_index))
        return last_index
        
    def lines(self, reverse=False, color=False, raw=False):
        if reverse:
            it = range(self.screen.lines - 1, -1, -1)
        else:
            it = range(self.screen.lines)
        for i in it:
            if raw:
                yield selt.get_raw_line(i)
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
        def is_article(data):
            last_line = self.get_line(self.screen.lines - 1)
            return rx.match(last_line)
        self.unt(is_article)
        
    def get_article(self, index):
        log.info("get {}th article".format(index))
        self.send(str(index) + "\r\r")
        is_animated = False
        def on_data(data):
            nonlocal is_animated
            if "這份文件是可播放的文字動畫".encode("big5-uao") in data:
                log.info("skip animation")
                self.send("n")
                is_animated = True
        self.unt("瀏覽 第", on_data=on_data)
        if is_animated:
            self.send("hq")
            self.unt("瀏覽 第")
            log.info("refresh animation page")
        if not self.article_configured:
            self.update_article_config()
        log.info("start collecting body")
        article = Article()
        rx_last_page = re.compile(r"瀏覽.+?\(100%\)".encode("big5-uao"))
        while True:
            line_start, line_end = article.add_screen(self.lines(raw=True))
            log.info("add screen {}~{}".format(line_start, line_end))
            # if line_start == 308:
                # set_trace()
            if rx_last_page.search(self.get_line(self.screen.lines - 1)):
                break
            self.send(" ")
            needle = "{}~{} 行".format(line_end + 1, line_end + self.screen.lines - 1)
            needle = needle.encode("big5-uao")
            def page_loaded(data):
                last_line = self.get_line(-1)
                return needle in last_line or rx_last_page.search(last_line)
            self.unt(page_loaded)
        self.send("q")
        log.info("get article success")
        return article.to_bytes()
        
def get_text(b):
    return re.sub().decode("big5-uao")
        
def main():
    parser = ArgumentParser(description="Backup PTT mail.")
    parser.add_argument("--user", help="username, otherwise prompt for the value.")
    parser.add_argument("--pass", dest="password", help="password, otherwise prompt for the value.")
    parser.add_argument("--dest", default=".", help="save to dest. Default to current dir.")
    range_group = parser.add_mutually_exclusive_group(required=True)
    range_group.add_argument(
        "--range", nargs=2, type=int, metavar=("START", "END"),
        help="specify a range (inclusive). Negative values and zeros are allowed, they are treated as (last_index + value) i.e. --range 0 0 would download the last mail."
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
   