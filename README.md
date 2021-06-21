# hibiki-scrapper

HiBiKi Radio Station scrapper

## What does this do?

1. Check for new episode for `Pastel＊Palettesのしゅわりんラジオ` in hibiki
2. Download, remux and archive episodes, including JSON file and images embedded in description
3. Generate "Podcast RSS file" and "Wikitext for MediaWiki" (template needed to render generated wikitext)
4. Send notification with WxPusher on success / error

## Requirements

You may need a Linux PC to make things easier.

* Common Linux tools `tar` and `xz` for archiving.
* Common Linux tools `wget` for simple image downloading  
  (TODO: use bundled downloader for this?)
* `ffmpeg` (https://ffmpeg.org) for remuxing.
* `mp4v2` (https://github.com/TechSmith/mp4v2) for MP4 (M4A) tagging.
* Python packages (see `requirements.txt`)
    * `requests` for network accessing
    * `m3u8` for m3u8 playlists patching

## How to run

1. Edit `config.json`.
    * Specify proxy if needed. (use `null` if you don't need any proxy)  
      see https://docs.python-requests.org/en/master/user/advanced/#proxies
    * Change WxPusher token and UID list, if you want to receive WeChat notifications.

2. Edit `handler_pstl.py`.
    * `AUDIO_DIR` directory for generated m4a audio.
    * `ARCHIVE_DIR` directory for archive (`.tar.xz`) files.
    * `PODCAST_FILE` podcast RSS file.
    * `AUDIO_URL_PREFIX` Web URL for your `AUDIO_DIR`, for wikitext and podcast.

3. Edit `run.sh` to fit your situation, and run it.

4. Additionally, add `run.sh` to `crontab` for periodically scrapping:

```shell
crontab -e
```

```shell
# Example of job definition:
# .---------------- minute (0 - 59)
# |  .------------- hour (0 - 23)
# |  |  .---------- day of month (1 - 31)
# |  |  |  .------- month (1 - 12) OR jan,feb,mar,apr ...
# |  |  |  |  .---- day of week (0 - 6) (Sunday=0 or 7) OR sun,mon,tue,wed,thu,fri,sat
# |  |  |  |  |
# *  *  *  *  * command to be executed
  1 16  *  *  1 /home/someone/hibiki/run.sh
```

## Files

`main.py` main entrance. Read config, check if any program has new episodes, call corresponding handler.

`handler_xxx.py` handler of downloading and archiving a specific program.

`hibiki.py` hibiki extractor.

`download.py` multi-threaded, resumable Amazon S3 downloader. (running in single-thread mode in this case)

`s3_etag.py` Amazon S3 Etag calculator.

`mp4tools.py` wrapper for `mp4v2`.

`wxpush.py` wrapper for WxPusher.

## Write your own handler

1. Find the program name.  
   e.g. https://hibiki-radio.jp/description/pstl/detail -> `pstl`

2. Create `handler_(program name).py`. Make sure to define function `run(data)` like this: (see `handler_pstl.py` for example)

```python
def run(data):
    # raw program json info, bytes
    info_raw: bytes = data['info_raw']
    # parsed json info
    info_json = data['info_json']
    # use this session to access internet
    session = data['session']
    # arbitrary data kept during runs. must be serializable to json 
    save: dict = data['save']  
```

3. Add your program name to `config.json` `[programs]` list.

4. It might be better to `raise` exceptions rather than sending notifications when debugging. See `def main()` in `main.py`.

## References

* Podcast specification from Google  
  https://support.google.com/googleplay/podcasts/answer/6260341

* Check if downloads from Amazon S3 is corrupted (somewhat)  
  https://stackoverflow.com/questions/12186993/what-is-the-algorithm-to-compute-the-amazon-s3-etag-for-a-file-larger-than-5gb

* WxPusher, a WeChat notification sender service  
  https://wxpusher.zjiecode.com/
