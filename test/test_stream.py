from ptt_mail_backup.byte_stream import ByteStream

def test_pattern():
    # https://github.com/eight04/ptt-mail-backup/issues/7
    match = ByteStream._text_pattern.match("\x9d\x9b")
    assert match
    assert match.group() == "\x9d\x9b"
    