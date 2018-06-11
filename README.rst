ptt-mail-backup
===============

.. image:: https://travis-ci.org/eight04/ptt-mail-backup.svg?branch=master
    :target: https://travis-ci.org/eight04/ptt-mail-backup

備份 PTT 站內信。不會再因為站內信打包失敗而把信箱塞爆一整個禮拜。

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

執行 `ptt-mail-backup -h`::

  usage: ptt-mail-backup [-h] [--user USER] [--pass PASSWORD] [--dest DEST]
                         [--verbose] [--filename-format FILENAME_FORMAT]
                         (--range START END | --all)

  Backup PTT mail.

  optional arguments:
    -h, --help            show this help message and exit
    --user USER           username, otherwise prompt for the value.
    --pass PASSWORD       password, otherwise prompt for the value.
    --dest DEST, -d DEST  save to dest. Default: '.'
    --verbose, -v         print verbose message.
    --filename-format FILENAME_FORMAT
                          filename format. Default: '{index}. [{board}] {title}
                          [{author}] ({time:%Y%m%d%H%M%S}).ans'
    --range START END, -r START END
                          specify a range (inclusive). Negative values and zeros
                          are allowed, they are treated as (last_index + value)
                          i.e. --range 0 0 would download the last mail.
    --all                 download all
    
或是 `python -m ptt_mail_backup`


Example
-------

下載所有信件到 2018-06-12 資料夾::

  ptt-mail-backup -d 2018-06-12 --all
  
下載最新的十封信件::

  ptt-mail-backup -r -9 0
  
從 CLI 傳入使用者名稱、密碼，並下載最舊的信件::

  ptt-mail-backup --user myusername --pass mypassword -r 1 1
      
Changelog
---------

* 0.1.0 (Next)

  - First release.
