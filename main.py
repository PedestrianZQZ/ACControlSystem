import sys

from PyQt5.QtGui import QIcon

from Admin_LogIn import *
from Waiter import *
from admin import *
from manager import *
from Record import *
from PyQt5.QtWidgets import QApplication, QMainWindow, QDialog, QMessageBox
from system_kernel import *

import socket
import threading
import time
import inspect
import ctypes

COLD = '1'  # 顾客请求空调设置参数
WARM = '2'
LOW = 1
MID = 2
HIGH = 3

COLDONLY = '1'  # 管理员空调运行模式设置
WARMONLY = '2'
COLDWARM = '3'

TIME_RATE = 5  # 5秒一个时钟周期
ADDRESS = ('127.0.0.1', 8009)  # socket接口
BUFSIZE: int = 1024  # socket消息缓冲区大小
STAFF_NOT_EXIST = "ERROR"  # 登录时判断账户是否存在

USER = '0'  # 用账号的第一位标识主体
WAITER = '1'
ADMIN = '2'
MANAGER = '3'

SUPERVISEMSG = '1'  # 管理员信令
INITSETMSG = '2'
POWERONMSG = '3'

STARTMSG = '1'  # 用户信令
STOPMSG = '2'
PAUSEMSG = '3'
RESUMEMSG = '4'
UPDATEMSG = '5'
CHANGEMSG = '6'
USERINITMSG = '7'

CHECKINMSG = '1'  # 服务员信令
CHECKOUTMSG = '2'
REFRESHMSG = '3'
BILLMSG = 'b'

GETLOGMSG = '1'  # 经理信令

RUNNINGMSG = '1'  # 房间信令
WAITINGMSG = '2'

SUCCESSMSG = '1'  # 通用信令
FAILMSG = '0'

ADDRESS = ('127.0.0.1', 8009)
BUFSIZE = 1024
sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sk.connect(ADDRESS)
msg_thread = threading.Thread()


def _async_raise(tid, exctype):
    """raises the exception, performs cleanup if needed"""
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")


def stop_thread(thread):
    _async_raise(thread.ident, SystemExit)


class parentWindow(QMainWindow):  # 主界面
    def __init__(self):
        QMainWindow.__init__(self)
        self.child3 = child3Window()
        self.child2 = child2Window()
        self.child1 = child1Window()
        self.main_ui = Ui_MainWindow()
        self.main_ui.setupUi(self)

        self.setWindowIcon(QIcon('./2.jpg'))
        self.window_pale = QtGui.QPalette()
        # self.window_pale.setColor(QPalette.Window, Qt.red)
        # self.main_ui.pushButton.setPalette(self.window_pale)
        self.window_pale.setBrush(self.backgroundRole(), QtGui.QBrush(QtGui.QPixmap('./2.jpg')))
        self.setPalette(self.window_pale)

        self.main_ui.pushButton.clicked.connect(self.word_get)

    def word_get(self):  # 登录函数
        login_user = self.main_ui.lineEdit.text()
        login_password = self.main_ui.lineEdit_2.text()

        msg = login_user + ' ' + login_password
        sk.sendall(msg.encode('utf-8'))
        feedback = sk.recv(BUFSIZE).decode('utf-8')
        print(feedback)
        if feedback == login_user + "登陆成功":
            if login_user == '1':
                self.child1.setWindowIcon(QIcon('./2.jpg'))
                self.child1.window_pale = QtGui.QPalette()
                # self.window_pale.setColor(QPalette.Window, Qt.red)
                # self.main_ui.pushButton.setPalette(self.window_pale)
                self.child1.window_pale.setBrush(self.backgroundRole(), QtGui.QBrush(QtGui.QPixmap('./2.jpg')))
                self.child1.setPalette(self.window_pale)
                self.child1.show()
                self.close()
            elif login_user == '2':
                self.child2.setWindowIcon(QIcon('./2.jpg'))
                self.child2.window_pale = QtGui.QPalette()
                # self.window_pale.setColor(QPalette.Window, Qt.red)
                # self.main_ui.pushButton.setPalette(self.window_pale)
                self.child2.window_pale.setBrush(self.backgroundRole(), QtGui.QBrush(QtGui.QPixmap('./2.jpg')))
                self.child2.setPalette(self.window_pale)
                self.child2.show()
                self.close()
            elif login_user == '3':
                self.child3.setWindowIcon(QIcon('./2.jpg'))
                self.child3.window_pale = QtGui.QPalette()
                # self.window_pale.setColor(QPalette.Window, Qt.red)
                # self.main_ui.pushButton.setPalette(self.window_pale)
                self.child3.window_pale.setBrush(self.backgroundRole(), QtGui.QBrush(QtGui.QPixmap('./2.jpg')))
                self.child3.setPalette(self.window_pale)
                self.child3.show()
                self.close()
        else:
            QMessageBox.warning(self,
                                "警告",
                                "用户名或密码错误！",
                                QMessageBox.Yes)


class child1Window(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        self.child = Ui_Dialog1()
        self.child4 = child4Window()
        self.child.setupUi(self)
        self.child.pushButton.clicked.connect(self.refresh)
        self.child.pushButton_2.clicked.connect(self.checkin)
        self.child.pushButton_3.clicked.connect(self.checkout)

    def refresh(self):
        msg = REFRESHMSG
        sk.sendall(msg.encode('utf-8'))
        feedback = sk.recv(BUFSIZE).decode('utf-8')
        print(feedback)
        self.child.refresh(feedback[12:].split(' '))

    def checkin(self):
        roomidin = self.child.lineEdit.text()
        msg = CHECKINMSG + ' ' + roomidin
        sk.sendall(msg.encode('utf-8'))
        feedback = sk.recv(BUFSIZE).decode('utf-8')
        print(feedback)

    def checkout(self):
        roomidout = self.child.lineEdit_2.text()
        msg = CHECKOUTMSG + ' ' + roomidout
        sk.sendall(msg.encode('utf-8'))
        feedback = sk.recv(BUFSIZE).decode('utf-8')
        print(feedback)
        self.child4.show()


class child2Window(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        self.child = Ui_Dialog2()
        self.child.setupUi(self)
        self.child.pushButton_3.clicked.connect(self.starting)
        self.child.pushButton_2.clicked.connect(self.apply)
        self.child.pushButton_4.clicked.connect(self.supervise)
        self.child.pushButton.clicked.connect(self.clear)

    # def retranslateUi(self):
    #     self.child.pushButton_3.clicked.connect(self.starting)
    #     self.child.pushButton_2.clicked.connect(self.apply)
    #     self.child.pushButton.clicked.connect(self.supervise)

    def starting(self):
        msg = POWERONMSG
        sk.sendall(msg.encode('utf-8'))
        feedback = sk.recv(BUFSIZE).decode('utf-8')
        print(feedback)
        if feedback == "system start!":
            QMessageBox.information(self,
                                    "提示",
                                    "系统开机成功！",
                                    QMessageBox.Yes)

    def supervise(self):
        msg = SUPERVISEMSG
        sk.sendall(msg.encode('utf-8'))
        feedback = sk.recv(BUFSIZE).decode('utf-8')
        print(feedback)
        global msg_thread
        msg_thread = threading.Thread(target=self.message_listen, args=(sk,))
        msg_thread.setDaemon(True)
        msg_thread.start()
        return msg_thread

    def message_listen(self, sk):
        while True:
            feedback = sk.recv(BUFSIZE).decode(encoding='utf8').split(' ')
            print(feedback)
            self.child.addmessage(feedback)

    def apply(self):
        mode = 0
        Mode = self.child.comboBox.currentText()
        if Mode == 'ColdOnly':
            mode = COLDONLY
        elif Mode == 'WarmOnly':
            mode = WARMONLY
        elif Mode == 'ColdWarm':
            mode = COLDWARM
        cold_low = self.child.lineEdit.text()
        warm_high = self.child.lineEdit_2.text()
        default_tem = self.child.lineEdit_3.text()
        high_price = self.child.lineEdit_4.text()
        mid_price = self.child.lineEdit_5.text()
        low_price = self.child.lineEdit_6.text()
        serve_num = self.child.lineEdit_7.text()
        wait_time = self.child.lineEdit_8.text()
        print(INITSETMSG + ' ' + cold_low + ' ' + warm_high + ' ' + default_tem + ' ' + serve_num + ' ' + mode \
              + ' ' + wait_time + ' ' + high_price + ' ' + mid_price + ' ' + low_price)
        msg = INITSETMSG + ' ' + cold_low + ' ' + warm_high + ' ' + default_tem + ' ' + serve_num + ' ' + mode \
              + ' ' + wait_time + ' ' + high_price + ' ' + mid_price + ' ' + low_price

        sk.sendall(msg.encode('utf-8'))
        feedback = sk.recv(BUFSIZE).decode('utf-8')
        if feedback == SUCCESSMSG:
            QMessageBox.information(self,
                                    "提示",
                                    "参数设置成功！",
                                    QMessageBox.Yes)
        print(feedback)

        # print(feedback.split(' '))
        # self.child.addmessage(feedback.split(' '))

    def clear(self):
        msg = '4'
        sk.sendall(msg.encode('utf-8'))
        global msg_thread
        stop_thread(msg_thread)
        self.child.stop_supervise()
        # feedback = sk.recv(BUFSIZE).decode('utf-8')
        # print(feedback)


class child3Window(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        self.child = Ui_Dialog3()
        self.child.setupUi(self)
        self.child.pushButton.clicked.connect(self.log_get)

    def log_get(self):
        QMessageBox.information(self,
                                "提示",
                                "生成报表成功！",
                                QMessageBox.Yes)
        log_data = self.child.lineEdit.text()
        msg = GETLOGMSG + ' ' + log_data
        sk.sendall(msg.encode('utf-8'))
        feedback = sk.recv(BUFSIZE).decode('utf-8')
        print(feedback)


class child4Window(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        self.child = Ui_dialog4()
        self.setWindowIcon(QIcon('./2.jpg'))
        self.window_pale = QtGui.QPalette()
        # self.window_pale.setColor(QPalette.Window, Qt.red)
        # self.main_ui.pushButton.setPalette(self.window_pale)
        self.window_pale.setBrush(self.backgroundRole(), QtGui.QBrush(QtGui.QPixmap('./2.jpg')))
        self.setPalette(self.window_pale)
        self.child.setupUi(self)
        self.child.pushButton.clicked.connect(self.bill_get)

    def bill_get(self):
        msg = BILLMSG
        sk.sendall(msg.encode('utf-8'))
        print(msg)
        feedback = sk.recv(BUFSIZE).decode('utf-8')
        self.child.bill_create(feedback[0:].split(','))
        print(feedback)


if __name__ == '__main__':
    ADDRESS = ('127.0.0.1', 8009)
    BUFSIZE = 1024
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sk.connect(ADDRESS)

    app = QApplication(sys.argv)
    window = parentWindow()
    window.show()
    sys.exit(app.exec_())
