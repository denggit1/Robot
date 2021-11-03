# coding:utf-8

from tkinter import Tk, Label, Spinbox, Button, DISABLED, NORMAL, END
from tkinter import PhotoImage, W, Listbox, font, Checkbutton, IntVar, Entry, StringVar, ACTIVE, NORMAL
from time import time, sleep, localtime, strftime
from wmi import WMI
from base64 import b64decode
from hmac import new
from hashlib import sha256
from requests import get
from talib import MACD
from numpy import array
from pandas import DataFrame
from threading import Thread
from playsound import playsound


# 背离类
class Deviation(object):
    # 初始化
    def __init__(self, ftime, host, symbol, kline, sleep_time, threshold_rate, log_func):
        """
        :param host: 主域名 @科学上网访问www.binance.com @国内网络访问www.binancezh.com
        :param symbol: BTCUSDT, ETHUSDT, BCHUSDT, ......
        :param kline: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, ......
        :param sleep_time: 刷新秒间隔
        :param threshold_rate: 阈值 - 0.001, 0.002, 0.003, 0.004, 0.005, 0.006, ......
        """
        self.ftime = ftime
        self.offset = True
        self.host, self.kline, self.threshold_rate = str(host), str(kline), float(threshold_rate)
        self.symbol, self.sleep = str(symbol), float(sleep_time)
        self.deviation_text = None
        self.end_time = 0
        self.log_func = log_func

    # 请求数据
    def request_data(self, host, symbol, interval):
        url = "https://{}/fapi/v1/klines?limit=1000&symbol={}&interval={}".format(host, symbol, interval)
        data = get(url, timeout=5).json()[:-1]
        return data

    # 处理数据
    def get_data_arr(self, data):
        df = DataFrame(data, columns=["otime", "open", "high", "low", "close",
                                      "volume", "ctime", "q-a-v", "n-o-t", "t-b-b-a-v", "t-b-q-a-v", "ignore"])
        df = df[["otime", "open", "high", "low", "close"]]
        df["dif"], df["dea"], df["macd"] = MACD(df["close"], fastperiod=12, slowperiod=26, signalperiod=9)
        df.dropna(inplace=True)
        data_arr = df.values
        return data_arr

    # 三维数组
    def get_ptp_pre_list(self, data_arr):
        # 判断红绿柱
        start_color = "green" if float(data_arr[0][-1]) > 0.0 else "red"
        # high, low, close, dif, macd
        all_list = [[
            [float(data_arr[0][2]), float(data_arr[0][3]), float(data_arr[0][4]),
             float(data_arr[0][5]), float(data_arr[0][7])],
        ], ]
        for each in data_arr[1:]:
            # high, low, close, dif, macd
            this_list = [float(each[2]), float(each[3]), float(each[4]), float(each[5]), float(each[7])]
            this_color = "green" if this_list[-1] > 0.0 else "red"
            # 柱色相同添加进同一个list中
            if this_color == start_color:
                all_list[-1].append(this_list)
            # 否则新建list
            else:
                all_list.append([this_list])
                start_color = this_color
        # ptp为pre的上个同色柱列表，mid为当前柱列表
        ptp_list = all_list[-4]
        pre_list = all_list[-2]
        mid_list = all_list[-1]
        return ptp_list, pre_list, mid_list

    # 计算背离
    def run_deviation(self, data):
        # 获取：prp, pre
        data_arr = self.get_data_arr(data)
        ptp_list, pre_list, mid_list = self.get_ptp_pre_list(data_arr)
        # high, low, close, dif, macd: 顶背离
        if pre_list[-1][-1] > 0.0:
            index_pre = array(pre_list)[:, 0].astype(float).argmax()
            index_ptp = array(ptp_list)[:, 0].astype(float).argmax()
            # 上根柱列表的最高价 > 上根柱同邻同色柱列表的最高价 且 两根最高价的DIF为相反
            # 当前DIF要大于一个阈值，收盘价*百分比 可得出 近似阈值
            if pre_list[index_pre][0] > ptp_list[index_ptp][0] and \
                    pre_list[index_pre][3] < ptp_list[index_ptp][3] and \
                    mid_list[0][3] > mid_list[0][2] * self.threshold_rate:
                if self.deviation_text != "顶信号开空":
                    self.deviation_text = "顶信号开空"
                    self.log_func(" 丨  {}  丨  {}   丨  {}  ".format(self.deviation_text, self.kline, self.symbol))
                    playsound(r"./sound/system.mp3")
        # high, low, close, dif, macd: 底背离
        else:
            index_pre = array(pre_list)[:, 1].astype(float).argmin()
            index_ptp = array(ptp_list)[:, 1].astype(float).argmin()
            if pre_list[index_pre][1] < ptp_list[index_ptp][1] and \
                    pre_list[index_pre][3] > ptp_list[index_ptp][3] and \
                    mid_list[0][3] < mid_list[0][2] * -self.threshold_rate:
                if self.deviation_text != "底信号开多":
                    self.deviation_text = "底信号开多"
                    self.log_func(" 丨  {}  丨  {}   丨  {}  ".format(self.deviation_text, self.kline, self.symbol))
                    playsound(r"./sound/system.mp3")

    # 启动
    def start(self):
        # self.log_func("目前监测 - 交易对与周期：{} {}".format(self.symbol, self.kline))
        while self.offset:
            try:
                # 主程序
                data = self.request_data(self.host, self.symbol, "5m" if self.kline == " 5m" else self.kline)
                etime = data[-1][0]
                if etime > self.end_time:
                    self.run_deviation(data)
                    self.end_time = etime
                # 验证激活码
                try:
                    this_time = strftime("%Y%m%d", localtime(
                        float(get("https://{}/fapi/v1/time".format(self.host)).json()["serverTime"]) / 1000.0))
                    if this_time >= self.ftime:
                        self.offset = False
                        self.log_func(" 丨  激活码过期  丨  {}   丨  {}  ".format(self.kline, self.symbol))
                except:
                    pass
            except Exception as e:
                pass
            sleep(self.sleep)


# GUI类
class MY_GUI():
    # 初始化
    def __init__(self, init_window_name):
        self.LOG_LINE_NUM = 0
        self.init_window_name = init_window_name

    # 设置窗口
    def set_init_window(self):
        # 窗口名
        edition = "1.0.1"
        self.init_window_name.title("AI智能预警系统_v{}".format(edition))
        # 290x160为窗口大小，+10 +10 定义窗口弹出时的默认展示位置
        self.init_window_name.geometry('720x480+600+200')
        self.init_window_name.resizable(0, 0)
        self.init_window_name.iconbitmap("./img/main.ico")
        # 窗口背景色，其他背景色见：blog.csdn.net/chl0000/article/details/7657887
        # self.init_window_name["bg"] = color
        # 虚化，值越小虚化程度越高
        # self.init_window_name.attributes("-alpha", 0.95)
        # 图片
        self.photo = PhotoImage(file="./img/ai.gif")
        self.init_data_label = Label(self.init_window_name, image=self.photo, height=85, width=720)
        self.init_data_label.grid(sticky=W)
        # 图片标签
        self.photo0 = PhotoImage(file="./img/user.gif")
        self.init_data_label_01 = Label(self.init_window_name, image=self.photo0, height=20, width=20)
        self.init_data_label_01.grid(row=1, padx=38, sticky=W, pady=5)
        self.init_data_label_0 = Label(self.init_window_name, text="欢迎您！",
                                       fg="Red", font=font.Font(size=11, weight=font.BOLD))
        self.init_data_label_0.grid(row=1, padx=62, sticky=W, pady=5)
        self.init_data_label_1 = Label(self.init_window_name, text="Ver {}".format(edition),
                                       fg="Red", font=font.Font(size=11, weight=font.BOLD))
        self.init_data_label_1.grid(row=1, padx=603, sticky=W, pady=5)
        # 标签
        self.init_data_label_2 = Label(self.init_window_name, text="选择系统：")
        self.init_data_label_2.grid(row=2, padx=38, sticky=W)
        self.init_spin_box_0 = Spinbox(self.init_window_name, state="readonly", wrap=True, width=16,
                                      values= ("AI预警机器人1号"))
        self.init_spin_box_0.grid(row=2, padx=103, sticky=W)
        # 标签
        self.init_data_label1 = Label(self.init_window_name, text="K线周期：")
        self.init_data_label1.grid(row=2, padx=270, sticky=W)
        self.init_spin_box1 = Spinbox(self.init_window_name, state="readonly", wrap=True, width=6,
                                      values= (" 5m", "15m"))
        self.init_spin_box1.grid(row=2, padx=330, sticky=W)
        # 标签
        self.init_data_label4 = Label(self.init_window_name, text="激活码：")
        self.init_data_label4.grid(row=2, padx=425, sticky=W)
        self.init_spin_box4 = Entry(self.init_window_name, width=15, show="*")
        self.init_spin_box4.grid(row=2, padx=475, sticky=W)
        # 按钮 and 调用内部方法  加()为直接调用
        self.str_trans_to_md5_button = Button(
            self.init_window_name, text="启动", bg="lightblue", width=10, command=self.str_trans_to_md5)
        self.str_trans_to_md5_button.grid(row=2, padx=603, sticky=W)
        # 日志框
        self.log_data_Text = Listbox(self.init_window_name, font=font.Font(size=15), state=DISABLED,
                                     bd=6, relief="ridge", width=63, height=11)
        self.log_data_Text.grid(sticky=W, padx=40, pady=10)
        # 显示设备码
        w = WMI()
        try:
            self.uuid = w.Win32_BaseBoard()[0].SerialNumber[-5:] + w.Win32_OperatingSystem()[0].SerialNumber[-5:] + \
                        edition.replace(".", "")
        except:
            self.uuid = None
        self.init_uuid0 = Label(self.init_window_name, text="设备码：")
        self.init_uuid0.grid(row=5, sticky=W, padx=40)
        sv = StringVar()
        sv.set("{}".format(self.uuid))
        self.init_uuid = Entry(self.init_window_name, relief="flat", state="readonly", textvariable=sv)
        self.init_uuid.grid(row=5, sticky=W, padx=90)
        # 复选框
        self.var0 = IntVar()
        self.check_button0 = Checkbutton(self.init_window_name, text="窗口透明",
                                         variable=self.var0, command=self.check_button_click0)
        self.check_button0.grid(row=5, sticky=W, padx=532)
        # 复选框
        self.var = IntVar()
        self.check_button = Checkbutton(self.init_window_name, text="窗口置顶",
                                        variable=self.var, command=self.check_button_click)
        self.check_button.grid(row=5, sticky=W, padx=612)
        # 标签
        self.init_data_label6 = Label(self.init_window_name, fg="DarkGoldenrod",
                                      text="系统信息：系统数据来源于 binance；                 "
                                           "AI智能预警系统 Ver {}；                  "
                                           "技术支持：***；".format(edition))
        self.init_data_label6.grid(row=6, padx=40, sticky=W)
        # 初始化
        self.log_data_Text.config(state=NORMAL)
        self.log_data_Text.insert(END, "       预警时间        丨   预警状态   丨  周期  丨  合约  ")
        self.LOG_LINE_NUM = self.LOG_LINE_NUM + 1
        self.log_data_Text.config(state=DISABLED)

    # 主函数
    def main(self):
        symbol_list = [
            'BTCUSDT', 'ETHUSDT', 'BCHUSDT', 'XRPUSDT', 'EOSUSDT', 'LTCUSDT', 'TRXUSDT', 'ETCUSDT',
            'LINKUSDT', 'XLMUSDT', 'ADAUSDT', 'XMRUSDT', 'DASHUSDT', 'ZECUSDT', 'XTZUSDT', 'BNBUSDT',
            'ATOMUSDT', 'ONTUSDT', 'IOTAUSDT', 'BATUSDT', 'VETUSDT', 'NEOUSDT', 'QTUMUSDT', 'IOSTUSDT',
            'THETAUSDT', 'ALGOUSDT', 'ZILUSDT', 'KNCUSDT', 'ZRXUSDT', 'COMPUSDT', 'OMGUSDT', 'DOGEUSDT'
        ]
        thread_result = []
        for symbol in symbol_list:
            dvt = Deviation(ftime=self.ftime, kline=self.kline, symbol=symbol, sleep_time="5", host=self.host,
                            threshold_rate=self.tr, log_func=self.write_log_to_Text)
            thread_result.append(Thread(target=dvt.start))
        for t in thread_result:
            t.setDaemon(True)
            t.start()
        # for t in thread_result:
        #     t.join()

    # 复选框变更
    def check_button_click0(self):
        if self.var0.get(): self.init_window_name.attributes("-alpha", 0.3)
        else: self.init_window_name.attributes("-alpha", 1.0)

    # 复选框变更
    def check_button_click(self):
        if self.var.get(): self.init_window_name.wm_attributes('-topmost', 1)
        else: self.init_window_name.wm_attributes('-topmost', 0)

    # 功能函数
    def str_trans_to_md5(self):
        self.kline, self.tr = self.init_spin_box1.get(), "0.005"
        # self.host, self.sys_key = "www.binancezh.com", self.init_spin_box4.get()
        self.host, self.sys_key = "fapi.binance.com", self.init_spin_box4.get()
        # 验证激活码
        try:
            this_time = strftime("%Y%m%d", localtime(
                float(get("https://{}/fapi/v1/time".format(self.host)).json()["serverTime"]) / 1000.0))
        except:
            self.write_log_to_Text(" 丨  网络未连通  丨  {}   丨  待定  ".format(self.kline))
            return
        temp = b64decode(self.sys_key).decode()
        key, ftime = temp[:10], temp[10:]
        signature = new(bytes(self.uuid.encode('utf-8')), bytes(ftime.encode('utf-8')),
                        digestmod=sha256).hexdigest()
        sign_key = signature[:5] + signature[-5:]
        # 验证判断
        if key == sign_key:
            if this_time < ftime:
                self.write_log_to_Text(" 丨  系统已激活  丨  {}   丨  待定  ".format(self.kline))
            else:
                self.write_log_to_Text(" 丨  激活码过期  丨  {}   丨  待定  ".format(self.kline))
                return
        else:
            self.write_log_to_Text(" 丨  激活码错误  丨  {}   丨  待定  ".format(self.kline))
            return
        # 运行
        self.ftime = ftime
        self.main()
        self.init_spin_box_0.config(state=DISABLED)
        self.init_spin_box1.config(state=DISABLED)
        self.init_spin_box4.config(state=DISABLED)
        self.str_trans_to_md5_button.config(state=DISABLED)

    # 获取当前时间
    def get_current_time(self):
        current_time = strftime('  %Y-%m-%d %H:%M:%S', localtime(time()))
        return current_time

    # 日志动态打印
    def write_log_to_Text(self, logmsg):
        current_time = self.get_current_time()
        logmsg_in = str(current_time) + " " + str(logmsg) + "\n"
        self.log_data_Text.config(state=NORMAL)
        if self.LOG_LINE_NUM <= 9:
            self.log_data_Text.insert(END, logmsg_in)
            self.LOG_LINE_NUM = self.LOG_LINE_NUM + 1
        else:
            self.log_data_Text.insert(END, logmsg_in)
            self.log_data_Text.delete(1)
        self.log_data_Text.config(state=DISABLED)


# 窗体函数
def gui_start():
    # 实例化出一个父窗口
    init_window = Tk()
    ZMJ_PORTAL = MY_GUI(init_window)
    # 设置根窗口默认属性
    ZMJ_PORTAL.set_init_window()
    # 父窗口进入事件循环，可以理解为保持窗口运行，否则界面不展示
    init_window.mainloop()


if __name__ == '__main__':
    gui_start()
