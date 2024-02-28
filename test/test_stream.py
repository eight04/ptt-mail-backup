from ptt_mail_backup.ptt_bot import PTTBot

def test_byte_stream():
    bot = PTTBot(None)
    text = "限".encode("big5-uao")

    bot.stream.feed(text)
    assert bot.dump_screen().strip() == "限"
