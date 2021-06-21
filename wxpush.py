#!/usr/bin/env python3

"""wxpush wrapper

doc: https://wxpusher.zjiecode.com/
"""

import time
import traceback
import base64
import sys

import requests

# from config import *

# don't edit this manually, rewritten with data from config.json
WxPusher_TOKEN = 'YOUR_TOKEN'
WxPusher_UIDs = ['YOUR_UID']


def sendNotification(content, summary=None, contentType=1):
    payload = {
        "appToken": WxPusher_TOKEN,
        "content": content,
        "summary": summary,
        "contentType": contentType,  # 内容类型 1 表示文字 2 表示html(只发送body标签内部的数据即可，不包括body标签) 3 表示markdown
        # "topicIds": [  # 发送目标的topicId，是一个数组！！！
        #     123
        # ],
        "uids": WxPusher_UIDs,
        # "url": "http:#wxpusher.zjiecode.com"  # 原文链接，可选参数
    }
    r = requests.post('https://wxpusher.zjiecode.com/api/send/message', json=payload, timeout=5)
    # print(r.json())


if __name__ == '__main__':
    import sys

    if len(sys.argv) <= 1:
        print(f'usage: {sys.argv[0]} [-b64] data')
        sys.exit(-1)
    msg = sys.argv[1]
    if msg == '-b64':
        msg = base64.b64decode(sys.argv[2].encode('latin1')).decode('utf-8')
    sendNotification(msg)
