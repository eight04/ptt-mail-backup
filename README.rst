ptt-mail-backup
===============

.. image:: https://travis-ci.org/eight04/ptt-mail-backup.svg?branch=master
    :target: https://travis-ci.org/eight04/ptt-mail-backup

一個用來備份 PTT 站內信的 CLI 工具。不會再因為站內信打包失敗而把信箱塞爆一整個禮拜。

Features
--------

* 使用 SSH 連上 PTT，再一頁頁爬
* 下載回來的檔案為 Big5-UAO 編碼
* 支援自動換行、寬度大於 80 的文章

Installation
------------

From `PYPI <https://pypi.org/project/ptt-mail-backup/>`__:

::

  pip install ptt-mail-backup

Usage
-----

執行 ``ptt-mail-backup ...``::

  usage: ptt-mail-backup [-h] [-u USER] [-p PASSWORD] [-d DEST] [-v]
                         [-f FILENAME_FORMAT] (-r START END | --all)

  Backup PTT mail.

  optional arguments:
    -h, --help            show this help message and exit
    -u USER, --user USER  username, otherwise prompt for the value.
    -p PASSWORD, --pass PASSWORD
                          password, otherwise prompt for the value.
    -d DEST, --dest DEST  save to dest. Default: '.'
    -v, --verbose         print verbose message.
    -f FILENAME_FORMAT, --filename-format FILENAME_FORMAT
                          filename format. Default: '{index}. [{board}] {title}
                          [{author}] ({time:%Y%m%d%H%M%S}).ans'
    -r START END, --range START END
                          specify a range (inclusive). Negative values and zeros
                          are allowed, they are treated as (last_index + value)
                          i.e. --range 0 0 would download the last mail.
    --all                 download all

或是 ``python -m ptt_mail_backup ...``。

範例
~~~~

下載所有信件到 2018-06-12 資料夾::

  ptt-mail-backup -d 2018-06-12 --all
  
下載最新的十封信件::

  ptt-mail-backup -r -9 0
  
從 CLI 傳入使用者名稱、密碼，並下載最舊的信件::

  ptt-mail-backup -u myusername -p mypassword -r 1 1
      
Changelog
---------

* 0.1.0 (Next)

  - First release.
