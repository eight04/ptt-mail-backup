import logging
import math
import re
from contextlib import contextmanager
from getpass import getpass

import uao
from paramiko.client import SSHClient, AutoAddPolicy

from .byte_screen import ByteScreen
from .byte_stream import ByteStream
from .article import match_foot, Article

uao.register_uao()

log = logging.getLogger(__name__)

RX_LAST_PAGE = re.compile(r"瀏覽.+?\(100%\)".encode("big5-uao"))

def is_no(text):
    return bool(re.match(r"\s*(n|no)\s*", text, re.I))
    
def parse_board_item(line):
    no, date, sender, title = (
        t.decode("big5-uao").strip()
        for t in (line[0:6], line[9:14], line[15:30], line[30:])
    )
    no = int(no.replace("●", "").strip())
    if title.startswith("轉"):
        title = "Fw:" + title[1:]
    elif title.startswith("◇"):
        title = title[2:]
    elif title.startswith("R:"):
        title = "Re:" + title[2:]
    return no, date, sender, title
    
@contextmanager
def ptt_login(user=None, password=None):
    with SSHClient() as client:
        client.set_missing_host_key_policy(AutoAddPolicy)
        client.connect("ptt.cc", username="bbs", password="")
        with client.invoke_shell() as channel:
            channel.settimeout(10)
            bot = PTTBot(channel)
            try:
                bot.login(user, password)
                yield bot
            except:
                log.info(
                    "uncaught error, here is the last screen:\n%s",
                    "\n".join(line.decode("big5-uao").rstrip() for line in bot.lines())
                )
                raise
    
class PTTBot:
    def __init__(self, channel):
        self.channel = channel
        self.screen = ByteScreen(80, 24)
        self.stream = ByteStream(self.screen)
        self.article_configured = False
        
    def login(self, user=None, password=None):
        if not user:
            user = input("User: ")
        if not password:
            password = getpass()
        self.unt("請輸入代號")
        
        log.info("start login")
        
        self.send(user + "\r" + password + "\r")
        def handle_login(data):
            if "刪除其他重複登入".encode("big5-uao") in data:
                self.send("n\r")
                
            if "密碼不對喔！".encode("big5-uao") in data:
                raise Exception("failed to login. Wrong password.")
        self.unt("按任意鍵繼續", on_data=handle_login)
        
        log.info("%s login success", user)
        
        self.send(" ")
        def handle_after_login(data):
            if "編輯器自動復原".encode("big5-uao") in data:
                raise Exception("failed to login. Unsaved article detected.")
                
            if "您要刪除以上錯誤嘗試的記錄嗎?".encode("big5-uao") in data:
                self.send("n\r")
                
            if "郵件已滿".encode("big5-uao") in data:
                self.send("qq")
        self.unt(self.detect("主功能表", 0), on_data=handle_after_login)
        log.info("enter main menu")
        
    def detect(self, needle, line_no):
        if needle.startswith("!"):
            reverse = True
            needle = needle[1:].encode("big5-uao")
        else:
            reverse = False
            needle = needle.encode("big5-uao")
        def callback(_data):
            if reverse:
                return needle not in self.get_line(line_no)
            return needle in self.get_line(line_no)
        return callback
        
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
            if "呼叫小天使".encode("big5-uao") in data:
                no, *_args = parse_board_item(self.get_line(self.screen.cursor.y))
                last_index = no
        self.unt("呼叫小天使", on_data=on_data)
        self.send("q")
        log.info("get last index success: %s", last_index)
        return last_index
        
    def lines(self, raw=False):
        for i in range(self.screen.lines):
            if raw:
                yield self.get_raw_line(i)
            else:
                yield self.get_line(i)
                
    def get_raw_line(self, line_no):
        if line_no < 0:
            line_no += self.screen.lines
        return [self.screen.buffer[line_no][i] for i in range(self.screen.columns)]

    def get_line(self, line_no):
        chars = self.get_raw_line(line_no)
        return "".join(c.data for c in chars).encode("latin-1")
        
    def update_article_config(self):
        """Update article config. It is hard to work with articles containing
        long lines (column > 80).
        """
        log.info("update pmore config")
        self.article_configured = True
        self.send("o")
        self.unt(self.on_pmore_conf)
        self.send("wmlq")
        self.unt(self.on_col(0))
        
    def on_pmore_conf(self, _data):
        return "piaip's more: pmore 2007+ 設定選項".encode("big5-uao") in self.get_line(-9)
        
    def on_col(self, col_no):
        def callback(_data):
            foot = match_foot(self.get_line(-1))
            return foot and foot.col_start == col_no
        return callback
        
    def get_article(self, index):
        log.info("get %sth article", index)
        self.send(str(index))
        self.unt("跳至第幾項")
        self.send("\r")
        self.unt(self.detect("!跳至第幾項", -1))
        curr_line = self.get_line(self.screen.cursor.y)
        _no, date, sender, title = parse_board_item(curr_line)
        
        log.info("title: %s", title)
        article = Article(date, sender, title)
        
        self.send("\r")
        
        is_animated = False
        def handle_animated(data):
            nonlocal is_animated
            if "這份文件是可播放的文字動畫".encode("big5-uao") in data:
                log.info("skip animation")
                self.send("n")
                is_animated = True
        self.unt(self.on_col(0), on_data=handle_animated)
        log.info("enter the article. is_animated=%s", is_animated)
        
        if is_animated:
            self.send("hq")
            self.unt(self.on_col(0))
            log.info("refresh animation page")
            
        if not self.article_configured:
            self.update_article_config()
            
        log.info("start collecting body")
        while True:
            screen = article.add_screen(self.lines(raw=True))
            log.info("add screen %s~%s", screen.line_start, screen.line_end)
            
            indent = 0
            while any(line.right_truncated for line in screen.lines):
                truncated_lines = set(line.line_no for line in screen.lines if line.right_truncated)
            
                log.info("has truncated right")
                indent += 1
                self.send(">")
                if screen.col_start == 0:
                    # the first indent is shorter
                    next_col = 7
                else:
                    next_col = screen.col_start + 8
                self.unt(self.on_col(next_col))
                screen = article.add_screen(
                    self.lines(raw=True),
                    skip_line=lambda line: line.line_no not in truncated_lines
                )
                log.info("move right to col %s", screen.col_start)
                # if screen.col_start == 136:
                    # set_trace()
                
            log.info("max indent %s", indent)
            if indent:
                self.send("<" * indent)
                self.unt(self.on_col(0))
                log.info("back to first col")
            
            if self.on_last_page():
                break
                
            self.send(" ")
            self.unt(lambda _data: (
                self.on_last_page() or self.on_line(screen.line_start + self.screen.lines - 2)
            ))
        self.send("q")
        
        log.info("get article success")
        return article
    
    def on_last_page(self):
        return RX_LAST_PAGE.search(self.get_line(-1))
        
    def on_line(self, line_no):
        foot = match_foot(self.get_line(-1))
        return foot and foot.line_start == line_no
