ptt-mail-backup
===============

.. image:: https://travis-ci.org/eight04/ptt-mail-backup.svg?branch=master
    :target: https://travis-ci.org/eight04/ptt-mail-backup
    
.. image:: https://codecov.io/gh/eight04/pyWorker/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/eight04/pyWorker

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

執行 `ptt-mail-backup -h`︰

.. code:: python

  usage: ptt-mail-backup [-h] [--user USER] [--pass PASSWORD] [--dest DEST]
                         [--verbose] (--range START END | --all)

  Backup PTT mail.

  optional arguments:
    -h, --help            show this help message and exit
    --user USER           username, otherwise prompt for the value.
    --pass PASSWORD       password, otherwise prompt for the value.
    --dest DEST, -d DEST  save to dest. Default to current dir.
    --verbose, -v         print verbose message.
    --range START END, -r START END
                          specify a range (inclusive). Negative values and zeros
                          are allowed, they are treated as (last_index + value)
                          i.e. --range 0 0 would download the last mail.
    --all                 download all
    
或是 `python -m ptt_mail_backup`

      
Changelog
---------

* 0.1.0 (Next)

  - First release.
