import argparse
import logging
import pathlib
from datetime import datetime

from ptt_article_parser import Article as ArticleParser
from ptt_article_parser.dir import DIR
from ptt_article_parser.rename import format_filename

from .ptt_bot import PTTBot

__version__ = "0.0.0"

class DummyDir(DIR):
    def __init__(self, article):
        super().__init__()
        self.article = article
        
    def getAuthor(self, _file):
        return self.article.sender
        
    def getTitle(self, _file):
        return self.article.title
        
    def getTime(self, _file):
        date = datetime.strptime(self.article.date, "%m/%d")
        date = datetime.today().replace(month=date.month, day=date.day)
        if date > datetime.today():
            date = date.replace(year=date.year - 1)
        return date

def main():
    parser = argparse.ArgumentParser(description="Backup PTT mail.")
    parser.add_argument(
        "-u", "--user", help="username, otherwise prompt for the value."
    )
    parser.add_argument(
        "-p", "--pass", dest="password", help="password, otherwise prompt for the value."
    )
    parser.add_argument(
        "-d", "--dest", default=".", help="save to dest. Default: %(default)r"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="print verbose message."
    )
    parser.add_argument(
        "-f", "--filename-format",
        default="{index}. [{board}] {title} [{author}] ({time:%Y%m%d%H%M%S}).ans",
        help="filename format. Default: %(default)r"
    )
    range_group = parser.add_mutually_exclusive_group(required=True)
    range_group.add_argument(
        "-r", "--range", nargs=2, type=int, metavar=("START", "END"),
        help="specify a range (inclusive). Negative values and zeros are "
             "allowed, they are treated as (last_index + value) i.e. --range 0 "
             "0 would download the last mail."
    )
    range_group.add_argument("--all", action="store_true", help="download all")
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level="INFO")
    
    with PTTBot(args.user, args.password) as bot:
        print("Login success, try entering your mail box")
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
                
            dest = pathlib.Path(args.dest)
            dest.mkdir(parents=True, exist_ok=True)
            for i in range(start, end + 1):
                print("Fetching mail: {}".format(i))
                article = bot.get_article(i)
                content = article.to_bytes()
                article_parser = ArticleParser(content)
                filename = format_filename(
                    article=article_parser,
                    format=args.filename_format,
                    dir=DummyDir(article),
                    extra={"index": i}
                )
                dest.joinpath(filename).write_bytes(content)
