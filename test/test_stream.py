from ptt_mail_backup.ptt_bot import PTTBot

def test_byte_stream():
    bot = PTTBot(None)
    text = "限".encode("big5-uao")

    bot.stream.feed(text)
    assert bot.dump_screen().strip() == "限"

    bot.stream.feed(b"\x1b[1;36mFOO")
    assert bot.dump_screen().strip() == "限FOO"
