import logging
import math
import re
from contextlib import contextmanager
from getpass import getpass

import uao
from paramiko.client import SSHClient, AutoAddPolicy

from .byte_screen import ByteScreen
from .byte_stream import ByteStream
from .article import Article

uao.register_uao()

log = logging.getLogger(__name__)

RX_LAST_PAGE = re.compile(r"瀏覽.+?\(100%\)".encode("big5-uao"))

# FIXME: only work with old cursor
RX_HIGHLIGHT_LINE = re.compile(r"\s*●\s*\d+".encode("big5-uao"))

LOGIN_VIEWS = [
    "本週五十大熱門話題",
    "本日十大熱門話題",
    "每小時上站人次統計",
    "本站歷史",
    "byte數   總 分",
    "大富翁 排行榜",
    "(←/q)"
]

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
        self.user = None
        
    def login(self, user=None, password=None):
        if not user:
            user = input("User: ")
        if not password:
            password = getpass()
        self.user = user
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
                
            elif re.search(r"您保存信件數目 \d+ 超出上限 \d+".encode("big5-uao"), data):
                self.send("qq")
                
            elif "新看板，確定要加入我的最愛嗎".encode("big5-uao") in data:
                self.send("y\r")
                
            elif any(view.encode("big5-uao") in data for view in LOGIN_VIEWS):
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
        should_stop = None
        if callable(needle):
            should_stop = needle
        else:
            def should_stop(data, test=needle.encode("big5-uao")): # pylint: disable=function-redefined
                log.debug("unt handler: %r", data)
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
        self.unt(self.detect("呼叫小天使", -1))
        self.send("q")
        self.unt("鴻雁往返")
        last_index, *_args = parse_board_item(self.get_highlight_line())
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
        self.unt(self.in_article())
        
    def on_pmore_conf(self, _data):
        return "piaip's more: pmore 2007+ 設定選項".encode("big5-uao") in self.get_line(-9)
        
    def article_refresh(self):
        self.send("h")
        self.unt(self.detect("呼叫小天使", -1))
        self.send("q")
        self.unt(self.in_article())
        
    def in_article(self):
        return self.detect("瀏覽 第", -1)
        
    def get_highlight_line(self):
        """Get the line starting with '●'"""
        for line in self.lines():
            if RX_HIGHLIGHT_LINE.match(line):
                return line
        raise Exception("Failed to find highlight line")
        
    def get_article(self, index):
        log.info("get %sth article", index)
        self.send(str(index))
        self.unt("跳至第幾項")
        self.send("\r")
        self.unt(self.detect("!跳至第幾項", -1))
        _no, date, sender, title = parse_board_item(self.get_highlight_line())
        
        log.info("title: %s", title)
        
        self.send("x" + self.user + "\r")
        self.unt(self.detect("標  題:", 2))
        title = self.get_line(2)[8:].strip()[:-5].strip().decode("big5-uao")
        self.send("n\r\x18a\r\r")
        self.unt(self.detect("郵件選單", 0))
        
        article = Article(date, sender, title)
        
        self.send("\r")
        
        is_animated = False
        def handle_animated(data):
            nonlocal is_animated
            if "這份文件是可播放的文字動畫".encode("big5-uao") in data:
                log.info("skip animation")
                self.send("n")
                is_animated = True
        self.unt(self.in_article(), on_data=handle_animated)
        log.info("enter the article. is_animated=%s", is_animated)
        
        if is_animated:
            self.article_refresh()
            log.info("refresh animation page to show ^L code")
            
        if not self.article_configured:
            self.update_article_config()
            
        log.info("start collecting body")
        y = 0
        x = 0
        while True:
            screen = article.add_screen([*self.lines(raw=True)][:-1], y, x)
            log.info("add screen %s~%s", y + 1, y + self.screen.lines - 1)
            
            indent = 0
            while any(line.right_truncated for line in screen.lines):
                truncated_lines = set(line.line_no for line in screen.lines if line.right_truncated)
            
                log.info("has truncated lines")
                indent_count = int(self.screen.columns / 8) - 1
                if x == 0:
                    # the first indent is shorter
                    x -= 1
                self.send(">" * indent_count)
                x += 8 * indent_count
                indent += indent_count
                self.article_refresh()
                screen = article.add_screen(
                    [*self.lines(raw=True)][:-1],
                    y,
                    x,
                    skip_line=lambda line: line.line_no not in truncated_lines
                )
                log.info("move right to col %s", x)
                
            log.info("max indent %s", indent)
            if indent:
                self.send("<" * indent)
                self.article_refresh()
                log.info("back to first col")
                x = 0

            # TODO: progress bar?
            log.debug(self.get_line(-1))
            
            if self.on_last_page():
                break
                
            self.send(":{}\r".format(y + 1 + self.screen.lines - 1))
            self.article_refresh()
            if not self.on_last_page():
                y += self.screen.lines - 1
                continue
                
            # return to y and find how many lines are left
            self.send(":{}\r".format(y + 1))
            self.article_refresh()
                
            scrolls = 0
            while not self.on_last_page():
                self.send("j")
                self.article_refresh()
                scrolls += 1
                
            y += scrolls
        self.send("q")
        
        log.info("get article success")
        return article
    
    def on_last_page(self):
        return RX_LAST_PAGE.search(self.get_line(-1))
