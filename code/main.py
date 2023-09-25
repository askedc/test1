import sys

import hjson
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QSize, QCoreApplication, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFontDatabase, QFont
from PyQt5.QtWidgets import QVBoxLayout, QPushButton, QHBoxLayout, QWidget, QLabel, QScrollArea, \
    QDialog

from utils import set_log_file, test_ddr, test_hdmi, test_cpu, play_sound, stop_sound, test_rtc, test_emmc_read, \
    test_emmc_write, test_sata, test_usb20, test_usb30, test_bt, test_wlan, test_eth, test_light, flash_lan_led, \
    test_edp, test_4G, test_nvme_read, test_nvme_write

CONFIG = "./config.hjson"

config = {
}


def load_config():
    global config
    with open(CONFIG, 'r', encoding='utf-8', ) as f:
        conf = f.read()
    config = hjson.loads(conf)
    if t := config.get('log_file'):
        set_log_file(t)


def get_test_item():
    test_item = [
        ('内存', "ddr"),
        ('CPU', "cpu"),
        ("HDMI1", "hdmi1"),
        ("HDMI2", "hdmi2"),
        ("eDP", "edp"),
        ("声音1", "sound1"),
        ("声音2", "sound2"),
        ('4G', "mobile"),
        ("RTC", "rtc"),
        ('SD card', "emmc"),
        ("USB2.0", "usb20"),
        ("USB3.0", "usb30"),
        ("SATA", "sata"),
        ("NVME", "nvme"),
        ("蓝牙", "bt"),
        ("以太网0", "eth0"),
        ("光口1", "eth1"),
        ("光口2", "eth2"),
        # ("以太网3", "eth3"),
        ("WLAN", "wlan"),
        ("刷入网口LED", "lan_led"),
        ("检查灯光", "check_light"),
        ("测试按钮", "test_button"),

    ]
    return [i for i in test_item if i[0] not in config.get('except_item', [])]


class SaveData:
    def __init__(self):
        self.serial_number = None


save_data = SaveData()


def label_set_font(label, size):
    font = QFont()
    font.setFamily("HarmonyOS Sans SC Medium")
    font.setPointSize(size)
    label.setFont(font)


def set_running(label):
    label.setText("RUNNING")
    label.setStyleSheet("color:#fff; background-color: blue;")
    QCoreApplication.processEvents()


def set_fail(label):
    label.setText("FAIL")
    label.setStyleSheet("color:#fff; background-color: red;")
    QCoreApplication.processEvents()


def set_pass(label):
    label.setText("PASS")
    label.setStyleSheet("color:#fff; background-color: green;")
    QCoreApplication.processEvents()


def default_text(text, res):
    text = str(text)
    layout = res.layout()
    if layout is not None:
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    else:
        layout = QVBoxLayout()
    l = QLabel(text)
    layout.addWidget(l)
    l.setStyleSheet("margin:0;padding:0;")
    label_set_font(l, config.get('font_size', 15))
    res.setLayout(layout)
    QCoreApplication.processEvents()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.test_funcs = [None] * len(get_test_item())

        self.setWindowTitle('Factory test')
        layout = QVBoxLayout()

        scrollArea = QScrollArea()
        scrollArea.setWidgetResizable(True)

        t = QWidget()
        first_line = QHBoxLayout()
        t.setLayout(first_line)
        first_line.addStretch()
        #
        # btn = QPushButton("Reset")
        # btn.setFixedSize(QSize(80, 50))
        # btn.setStyleSheet("background-color: #ccc")
        # label_set_font(btn, config.get('font_size', 15))
        # first_line.addWidget(btn, alignment=Qt.AlignRight)
        t.setStyleSheet("background-color: #999")
        checkbox = QtWidgets.QCheckBox('auto', self)
        label_set_font(checkbox, config.get('font_size', 15))
        first_line.addWidget(checkbox, alignment=Qt.AlignRight)
        if config.get('auto', False):
            self.auto = True
            checkbox.setCheckState(Qt.Checked)
        else:
            self.auto = False
            checkbox.setCheckState(Qt.Unchecked)
        checkbox.stateChanged.connect(self.auto_change)
        layout.addWidget(t)

        self.set_test_item(layout)
        layout.addStretch(1)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        widget = QWidget()
        widget.setLayout(layout)
        scrollArea.setWidget(widget)
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(scrollArea)
        mainLayout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(mainLayout)
        # self.showMaximized()
        self.resize(1920, 1080)

    def auto_change(self, state):
        if state == Qt.Checked:
            self.auto = True
        else:
            self.auto = False

    def set_test_item(self, layout):
        start_num = 1
        for text, call in get_test_item():

            t = QWidget()
            line = QHBoxLayout()
            t.setLayout(line)
            label = QWidget()
            label.setContentsMargins(0, 0, 0, 0)
            default_text(str(start_num) + '. ' + text, label)
            line.addWidget(label, alignment=Qt.AlignLeft)
            line.addStretch(1)
            res = QWidget()
            res.setContentsMargins(0, 0, 0, 0)

            line.addWidget(res, alignment=Qt.AlignRight)
            btn = QPushButton("Test")
            btn.setFixedSize(QSize(100, 50))
            btn.setStyleSheet("background-color: #ccc")
            label_set_font(btn, config.get('font_size', 15))
            line.addWidget(btn, alignment=Qt.AlignRight)

            label = QLabel("")
            label.setFixedWidth(150)
            label.setFixedHeight(60)
            label.setAlignment(Qt.AlignCenter)
            label_set_font(label, config.get('font_size', 15))
            line.addWidget(label, alignment=Qt.AlignRight)
            if start_num & 1:
                t.setStyleSheet("background-color: #ccc;padding: 12px;")
            else:
                t.setStyleSheet("background-color: #fff;padding: 12px;")
            self.test_funcs[start_num - 1] = self.__getattribute__(call)(res, btn, label, start_num - 1)
            btn.clicked.connect(self.test_funcs[start_num - 1])
            line.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(t, alignment=Qt.AlignTop)
            start_num += 1

    def run_next(self, now_number):
        QCoreApplication.processEvents()
        if self.auto and len(self.test_funcs) - 1 != now_number:
            self.test_funcs[now_number + 1]()

    def ddr(self, res, btn, label, now_number):
        """3.RAM"""

        def change():
            set_running(label)
            r = test_ddr(config['tests']['ddr']['gt'], config['tests']['ddr']['lt'])
            if r:
                set_fail(label)
                default_text(f"code {r}", res)
            else:
                set_pass(label)
                self.run_next(now_number)

        return change

    def cpu(self, res, btn, label, now_number):
        """2.cpu"""

        def change():
            set_running(label)
            r = test_cpu(config['tests']['cpu']['freq'], config['tests']['cpu']['model'])
            if r:
                set_fail(label)
                default_text(f"code {r}", res)
            else:
                set_pass(label)
                self.run_next(now_number)

        return change

    def hdmi1(self, res, btn, label, now_number):
        """hdmi"""

        def change():
            set_running(label)
            r = test_hdmi(config['tests']["HDMI1"]['size'], config['tests']["HDMI1"]['devices'])
            if r:
                set_fail(label)
                default_text(f"code {r}", res)
            else:
                set_pass(label)
                self.run_next(now_number)

        return change

    def hdmi2(self, res, btn, label, now_number):
        """hdmi"""

        def change():
            set_running(label)
            r = test_hdmi(config['tests']["HDMI2"]['size'], config['tests']["HDMI2"]['devices'])
            if r:
                set_fail(label)
                default_text(f"code {r}", res)
            else:
                set_pass(label)
                self.run_next(now_number)

        return change

    def edp(self, res, btn, label, now_number):
        """edp"""

        def change():
            set_running(label)
            r = test_edp(config['tests']["eDP"]['size'], config['tests']["eDP"]['devices'])
            if r:
                set_fail(label)
                default_text(f"code {r}", res)
            else:
                set_pass(label)
                self.run_next(now_number)

        return change

    def sound1(self, res, btn, label, now_number):
        def pass_clc():
            stop_sound("PASS", 1)
            set_pass(label)
            result_dialog.close()
            self.run_next(now_number)

        def fail_clc():
            stop_sound("FAIL", 1)
            set_fail(label)
            result_dialog.close()

        result_dialog = QDialog()
        result_dialog.setWindowTitle('是否听到声音')
        result_dialog.setWindowFlags(Qt.WindowTitleHint | Qt.WindowStaysOnTopHint)
        layout = QVBoxLayout()
        result_dialog.setLayout(layout)

        l = QLabel("是否听到声音")
        label_set_font(l, config.get('font_size', 15))

        layout.addWidget(l)

        h_layout = QHBoxLayout()
        layout.addLayout(h_layout)
        btn = QPushButton("pass")
        btn.setFixedSize(QSize(160, 80))
        btn.setStyleSheet("background-color: green;  border: 1px solid black;")
        btn.clicked.connect(pass_clc)
        label_set_font(btn, config.get('font_size', 15))
        h_layout.addWidget(btn)

        btn = QPushButton("fail")
        btn.setFixedSize(QSize(160, 80))
        btn.setStyleSheet("background-color: red;  border: 1px solid black;")
        btn.clicked.connect(fail_clc)
        label_set_font(btn, config.get('font_size', 15))
        h_layout.addWidget(btn)

        def change():
            play_sound()
            result_dialog.exec_()

        return change

    def sound2(self, res, btn, label, now_number):
        def pass_clc():
            stop_sound("PASS", 2)
            set_pass(label)
            result_dialog.close()
            self.run_next(now_number)

        def fail_clc():
            stop_sound("FAIL", 2)
            set_fail(label)
            result_dialog.close()

        result_dialog = QDialog()
        result_dialog.setWindowTitle('是否听到声音')
        result_dialog.setWindowFlags(Qt.WindowTitleHint | Qt.WindowStaysOnTopHint)
        layout = QVBoxLayout()
        result_dialog.setLayout(layout)

        l = QLabel("是否听到声音")
        label_set_font(l, config.get('font_size', 15))

        layout.addWidget(l)

        h_layout = QHBoxLayout()
        layout.addLayout(h_layout)
        btn = QPushButton("pass")
        btn.setFixedSize(QSize(160, 80))
        btn.setStyleSheet("background-color: green;  border: 1px solid black;")
        btn.clicked.connect(pass_clc)
        label_set_font(btn, config.get('font_size', 15))
        h_layout.addWidget(btn)

        btn = QPushButton("fail")
        btn.setFixedSize(QSize(160, 80))
        btn.setStyleSheet("background-color: red;  border: 1px solid black;")
        btn.clicked.connect(fail_clc)
        label_set_font(btn, config.get('font_size', 15))
        h_layout.addWidget(btn)

        def change():
            play_sound("plughw:0,7")
            result_dialog.exec_()

        return change

    def mobile(self, res, btn, label, now_number):

        def change():
            set_running(label)
            r = test_4G()
            if r:
                set_fail(label)
                default_text(f"code {r}", res)
            else:
                set_pass(label)
                self.run_next(now_number)

        return change

    def rtc(self, res, btn, label, now_number):
        def change():
            set_running(label)
            r = test_rtc()
            if r:
                set_fail(label)
                default_text(f"code {r}", res)
            else:
                set_pass(label)
                self.run_next(now_number)

        return change

    def emmc(self, res, btn, label, now_number):
        def change():
            set_running(label)
            default_text("read", res)
            r1 = test_emmc_read(config['tests']['emmc']['read'])
            default_text("write", res)
            r2 = test_emmc_write(config['tests']['emmc']['write'])
            if r1 or r2:
                set_fail(label)
                default_text(f"code R:{r1} W:{r2}", res)
            else:
                set_pass(label)
                self.run_next(now_number)

        return change

    def usb20(self, res, btn, label, now_number):
        def change():
            set_running(label)

            r = test_usb20(config['tests']['usb20']['read'], config['tests']['usb20']['write'])
            if r:
                set_fail(label)
                default_text(f"code {r}", res)
            else:
                set_pass(label)
                self.run_next(now_number)

        return change

    def usb30(self, res, btn, label, now_number):
        def change():
            set_running(label)

            r = test_usb30(config['tests']['usb30']['read'], config['tests']['usb30']['write'])
            if r:
                set_fail(label)
                default_text(f"code {r}", res)
            else:
                set_pass(label)
                self.run_next(now_number)

        return change

    def sata(self, res, btn, label, now_number):
        def change():
            set_running(label)

            r = test_sata(config['tests']['sata']['count'], config['tests']['sata']['read'],
                          config['tests']['sata']['write'])
            if r:
                set_fail(label)
                default_text(f"code {r}", res)
            else:
                set_pass(label)
                self.run_next(now_number)

        return change

    def nvme(self, res, btn, label, now_number):
        def change():
            set_running(label)
            default_text("read", res)
            r1 = test_nvme_read(config['tests']['nvme']['read'])
            default_text("write", res)
            r2 = test_nvme_write(config['tests']['nvme']['write'])
            if r1 or r2:
                set_fail(label)
                default_text(f"code R:{r1} W:{r2}", res)
            else:
                set_pass(label)
                self.run_next(now_number)
            ...
        return change

    def bt(self, res, btn, label, now_number):
        def change():
            set_running(label)

            r = test_bt()
            if r:
                set_fail(label)
                default_text(f"code {r}", res)
            else:
                set_pass(label)
                self.run_next(now_number)

        return change

    def eth0(self, res, btn, label, now_number):
        def change():
            set_running(label)

            r = test_eth(config['tests']["eth0"]["speed"], "ETH0", "ether0", config['tests']["eth0"]["server_ip"])
            if r:
                set_fail(label)
                default_text(f"code {r}", res)
            else:
                set_pass(label)
                self.run_next(now_number)

        return change

    def eth1(self, res, btn, label, now_number):
        def change():
            set_running(label)

            r = test_eth(config['tests']["eth1"]["speed"], "ETH1", "ether1", config['tests']["eth1"]["server_ip"])
            if r:
                set_fail(label)
                default_text(f"code {r}", res)
            else:
                set_pass(label)
                self.run_next(now_number)

        return change

    def eth2(self, res, btn, label, now_number):
        def change():
            set_running(label)

            r = test_eth(config['tests']["eth2"]["speed"], "ETH2", "ether2", config['tests']["eth2"]["server_ip"])
            if r:
                set_fail(label)
                default_text(f"code {r}", res)
            else:
                set_pass(label)
                self.run_next(now_number)

        return change

    def eth3(self, res, btn, label, now_number):
        def change():
            set_running(label)

            r = test_eth(config['tests']["eth"]["speed"], "ETH3", "ether3", config['tests']["eth"]["server_ip"])
            if r:
                set_fail(label)
                default_text(f"code {r}", res)
            else:
                set_pass(label)
                self.run_next(now_number)

        return change

    def wlan(self, res, btn, label, now_number):
        def change():
            set_running(label)

            r = test_wlan(config['tests']["wlan"]["ssid"], config['tests']["wlan"]["password"],
                          config['tests']["wlan"]["speed"], config['tests']["wlan"]["server_ip"])
            if r:
                set_fail(label)
                default_text(f"code {r}", res)
            else:
                self.run_next(now_number)
                set_pass(label)

        return change

    def lan_led(self, res, btn, label, now_number):
        def change():
            set_running(label)

            r = flash_lan_led()

            if r:
                set_fail(label)
                default_text(f"code {r}", res)
            else:
                set_pass(label)
                self.run_next(now_number)

        return change

    def check_light(self, res, btn, label, now_number):
        def pass_clc():
            test_light("PASS")
            set_pass(label)
            result_dialog.close()
            self.run_next(now_number)

        def fail_clc():
            test_light("FAIL")
            set_fail(label)
            result_dialog.close()

        result_dialog = QDialog()
        result_dialog.setWindowTitle('检查灯光')
        result_dialog.setWindowFlags(Qt.WindowTitleHint | Qt.WindowStaysOnTopHint)
        layout = QVBoxLayout()
        result_dialog.setLayout(layout)

        l = QLabel("网口灯 电源灯 等 是否正常？")
        label_set_font(l, config.get('font_size', 15))

        layout.addWidget(l)

        h_layout = QHBoxLayout()
        layout.addLayout(h_layout)
        btn = QPushButton("pass")
        btn.setFixedSize(QSize(160, 80))
        btn.setStyleSheet("background-color: green;  border: 1px solid black;")
        btn.clicked.connect(pass_clc)
        label_set_font(btn, config.get('font_size', 15))
        h_layout.addWidget(btn)

        btn = QPushButton("fail")
        btn.setFixedSize(QSize(160, 80))
        btn.setStyleSheet("background-color: red;  border: 1px solid black;")
        btn.clicked.connect(fail_clc)
        label_set_font(btn, config.get('font_size', 15))
        h_layout.addWidget(btn)

        def change():
            result_dialog.exec_()

        return change

    def test_button(self, res, btn, label, now_number):
        class WaitButton(QThread):
            progress_signal = pyqtSignal(int)

            def run(self) -> None:
                from evdev import InputDevice, categorize, ecodes
                # 打开输入设备
                dev = InputDevice('/dev/input/event1')
                pri = 0
                times = 0
                for event in dev.read_loop():
                    if event.type == ecodes.EV_KEY:
                        key_state = categorize(event)
                        key_code = key_state.keycode

                        if key_state.keystate == key_state.key_down:
                            self.progress_signal.emit(0)

        btn_thr = WaitButton()
        timer = QTimer()

        def success():
            set_pass(label)
            default_text("", res)
            timer.stop()

        def fail():
            set_fail(label)
            default_text("超时", res)
            btn_thr.exit(0)

        def change():
            default_text("请点击电源键", res)
            btn_thr.start()
            btn_thr.progress_signal.connect(success)
            timer.timeout.connect(fail)
            timer.start(10000)

        return change


def add_fonts():
    fontDb = QFontDatabase()
    fontDb.addApplicationFont("fonts/HarmonyOS_Sans_SC_Medium.ttf")


if __name__ == '__main__':
    load_config()
    app = QtWidgets.QApplication(sys.argv)
    add_fonts()
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
