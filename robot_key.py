# coding: utf-8

from time import strftime
from hmac import new
from hashlib import sha256
from base64 import b64encode
from os import system
from pyperclip import copy

try:
    pwd = input("\n请输入登录密码：")
    system("cls")
    need_sha, this_time = pwd[:6], pwd[6: 10]
    sha = sha256(need_sha.encode('utf-8'))
    key = sha.hexdigest() + this_time
    sys_key = "789359605735201dfdbf6374e1e384611d081e6727c9cc2ee889ec6e22c7d07c" + strftime("%H%M")
    if key == sys_key:
        print("\n登录成功！")
        offset = 1
        while offset:
            uuid = input("\n请输入设备码（*************）：")
            ymd = input("\n请输入到期年月日（20200801）：")
            signature = new(bytes(uuid.encode('utf-8')), bytes(ymd.encode('utf-8')), digestmod=sha256).hexdigest()
            data = b64encode((signature[:5] + signature[-5:] + ymd).encode('utf-8')).decode()
            copy(data)
            print("\n您的激活码已为您复制到剪贴板：{}".format(data))
            offset = int(input("\n是否继续生成激活码（1， 0）："))
    else:
        print("\n密码错误！")
except:
    print("\n异常退出！")
input("\n按任意键退出程序！")
