import argparse
import logging
import pathlib

import uao

from .ptt_bot import PTTBot

__version__ = "0.0.0"

uao.register_uao()

# log = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Backup PTT mail.")
    parser.add_argument(
        "--user", help="username, otherwise prompt for the value."
    )
    parser.add_argument(
        "--pass", dest="password", help="password, otherwise prompt for the value."
    )
    parser.add_argument(
        "--dest", "-d", default=".", help="save to dest. Default to current dir."
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="print verbose message."
    )
    range_group = parser.add_mutually_exclusive_group(required=True)
    range_group.add_argument(
        "--range", "-r", nargs=2, type=int, metavar=("START", "END"),
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
                content = bot.get_article(i)
                file = dest.joinpath("ptt_mail_backup_{}.ans".format(i))
                file.write_bytes(content)
