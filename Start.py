import sys

from mainWindow import *
from userWindow import *
from PyQt5.QtWidgets import QApplication, QMainWindow, QDialog, QMessageBox
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtGui import QIcon

import threading
import socket
import time
import queue

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

GETLOGMSG = '1'  # 经理信令

RUNNINGMSG = '8'  # 房间信令
WAITINGMSG = '9'

SUCCESSMSG = '1'  # 通用信令
FAILMSG = '0'

g_conn_pool_dict = {}  # 连接池
g_socket_server = None  # socket对象
staff_dict = {'0': '123456', '1': '123456', '2': '123456', '3': '123456'}  # 工作人员信息,1开头表示服务员，2开头表示管理员，3开头表示经理
spare_room_list = ['0401', '0402', '0403', '0404', '0405', '0406', '0407', '0408', '0409', '0410']
room_dict = {}

ac = None  # 空调系统对象
que = queue.Queue()


class Request:
    """
    params
    id: 房间号
    tem: 温度
    speed: 风速
    mode: 模式
    """
    id = 0
    tem = 0.0
    speed = 0
    mode = None

    def __init__(self, id, mode, tem, speed):
        self.id = id
        self.tem = tem
        self.speed = speed
        self.mode = mode


def find_request_by_id(request: Request, queue):
    for index, item in enumerate(queue):
        if item.id == request.id:
            return index
    return False


class Room:
    isopen = False
    request_state = None
    id = None
    room_tem = None
    ac_tem = None
    ac_speed = None
    ac_mode = None
    fee = None

    def __init__(self, id, room_tem, set_tem, set_speed, set_mode):
        self.id = id
        self.room_tem = room_tem
        self.ac_tem = set_tem
        self.ac_speed = set_speed
        self.ac_mode = set_mode

    def check_in(self, tem):
        self.isopen = True
        self.room_tem = tem
        self.ac_tem = tem
        self.ac_speed = MID
        self.ac_mode = COLD

    def check_out(self):
        self.isopen = False
        self.id = None
        room_tem = None
        set_tem = None
        set_speed = None
        set_mode = None

    def get_ac_info(self):
        tem = self.ac_tem
        speed = self.ac_speed
        mode = self.ac_mode
        return tem, speed, mode


# 前面都是系统内核的

class Listener:
    def message_listen(self, sk):  # 监听主机消息的函数
        global room
        global cold_low
        global warm_high
        global default_tem
        global room_default_tem
        while True:
            feedback = sk.recv(BUFSIZE).decode('utf-8')
            print("收到：", feedback)
            if feedback == RUNNINGMSG:
                w.child.child.label_7.setText('正在送风')
                room.request_state = RUNNINGMSG
            elif feedback == WAITINGMSG:
                w.child.child.label_7.setText('等待')
                room.request_state = WAITINGMSG
            elif feedback == UPDATEMSG:
                print(end='')
            elif feedback == PAUSEMSG:
                w.child.child.label_7.setText('暂停送风')
                room.request_state = WAITINGMSG
            elif feedback == w.id + "登陆成功":
                w.child.child.pushButton.clicked.connect(w.start_respon)
                socket_semaphore.acquire()
                sk.sendall(USERINITMSG.encode('utf-8'))
                print("发出：", USERINITMSG)
                socket_semaphore.release()

                feedback = sk.recv(BUFSIZE).decode('utf-8')
                print("收到：", feedback)
                infoArr = feedback.strip().split(' ')
                room.id = w.id
                default_tem = int(infoArr[0])
                cold_low = int(infoArr[1])
                warm_high = int(infoArr[2])
                mode = int(infoArr[3])
                room.room_tem = float(infoArr[4])
                room_default_tem = room.room_tem
                room.ac_tem = default_tem
                room.ac_mode = COLD
                room.ac_speed = MID

            if feedback == STOPMSG:
                room.isopen = False
                room.request_state = WAITINGMSG
                w.child.child.label_7.setText('停止运行')


class Sender:
    time_new = None

    def send_request(self, sk):  # 发送1秒内最后一条修改请求
        while True:
            threadLock.acquire()  # 实现线程同步
            global change_flag
            global change_request_msg
            global time_old
            global que
            time_new = time.time()
            if change_flag == 1 and time_new - time_old > 1:
                socket_semaphore.acquire()
                sk.sendall(change_request_msg.encode('utf-8'))
                print("发出：", change_request_msg)
                socket_semaphore.release()
                change_flag = 0
                que.put('send')
            threadLock.release()
            time.sleep(0.1)


class TemComputer:
    def compute_tem(self, sk):  # 计算温度线程的函数
        global room
        global change_flag
        global arrive_flag
        time_start = time.time()  # 开始时间
        room.room_tem = float(room.room_tem)
        room.ac_tem = float(room.ac_tem)
        while True:
            threadLock.acquire()  # 实现线程同步
            time_end = time.time()  # 当前时间
            if room.ac_tem > room.room_tem:
                direction = WARM  # 修改
            elif room.ac_tem < room.room_tem:
                direction = COLD
            else:
                direction = None
            if int(time_end - time_start) % TIME_RATE == 0:  # 5秒更新一次时间
                if room.request_state == RUNNINGMSG:  # 请求状态成功
                    if direction == WARM:
                        if room.ac_speed == LOW:
                            room.room_tem += 0.4
                        elif room.ac_speed == MID:
                            room.room_tem += 0.5
                        elif room.ac_speed == HIGH:
                            room.room_tem += 0.6
                    elif direction == COLD:
                        if room.ac_speed == LOW:
                            room.room_tem -= 0.4
                        elif room.ac_speed == MID:
                            room.room_tem -= 0.5
                        elif room.ac_speed == HIGH:
                            room.room_tem -= 0.6
                elif room.request_state == WAITINGMSG:  # 请求状态失败
                    if room.room_tem < room_default_tem:
                        room.room_tem += 0.5
                    elif room.room_tem > room_default_tem:
                        room.room_tem -= 0.5
                    # room.room_tem += 0.5
            room.room_tem = round(room.room_tem, 1)
            msg = UPDATEMSG + ' ' + str(room.room_tem) + ' ' + str(int(room.ac_tem)) + ' ' + str(
                room.ac_speed) + ' ' + str(room.ac_mode)
            socket_semaphore.acquire()
            sk.sendall(msg.encode('utf-8'))
            print("发出：", msg)
            socket_semaphore.release()

            room.room_tem = round(room.room_tem, 1)
            if room.isopen == True and room.request_state == RUNNINGMSG and (
                    (direction == COLD and float(room.room_tem) <= float(room.ac_tem)) or (
                    direction == WARM and float(room.room_tem) >= float(room.ac_tem))):  # 如果达到目标温度，发送暂停消息
                msg = PAUSEMSG
                socket_semaphore.acquire()
                sk.sendall(msg.encode('utf-8'))
                print("发出：", msg)
                socket_semaphore.release()
                arrive_flag = 1

            if room.isopen == True and room.request_state == WAITINGMSG and arrive_flag == 1 and (
                    (room.room_tem <= float(room.ac_tem) - 1) or (room.room_tem >= float(room.ac_tem) + 1)):
                msg = RESUMEMSG
                socket_semaphore.acquire()
                sk.sendall(msg.encode('utf-8'))
                print("发出：", msg)
                socket_semaphore.release()
                arrive_flag = 0
            threadLock.release()
            time.sleep(TIME_RATE)


class parentWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.main_ui = Ui_MainWindow()
        self.setFixedSize(675, 500)
        self.main_ui.setupUi(self)
        self.setWindowIcon(QIcon('./1.jpg'))
        self.window_pale = QtGui.QPalette()
        self.window_pale.setBrush(self.backgroundRole(), QtGui.QBrush(QtGui.QPixmap('./1.jpg')))
        self.setPalette(self.window_pale)
        self.main_ui.pushButton.clicked.connect(self.create_user)

    def create_user(self):
        self.child = childWindow()
        self.child.setFixedSize(600, 500)
        self.child.setWindowIcon(QIcon('./1.jpg'))
        self.child.child.room_id = self.main_ui.lineEdit.text()
        self.child.child.label_2.setText(self.child.child.room_id)
        self.child.window_pale = QtGui.QPalette()
        self.child.window_pale.setBrush(self.child.backgroundRole(), QtGui.QBrush(QtGui.QPixmap('./2.jpg')))
        self.child.setPalette(self.child.window_pale)
        self.child.show()
        self.close()
        self.id = str(self.child.child.room_id)
        self.password = self.child.child.room_id
        if self.id != '':
            self.msg = self.id + ' ' + self.password
            socket_semaphore.acquire()
            sk.sendall(self.msg.encode('utf-8'))
            print("发出：", self.msg)
            socket_semaphore.release()
            the_listener = Listener()
            the_tem_computer = TemComputer()
            the_sender = Sender()
            msg_thread = threading.Thread(target=self.req, args=(que,))
            msg_thread.setDaemon(True)
            msg_thread.start()

            msg_thread = threading.Thread(target=the_listener.message_listen, args=(sk,))
            msg_thread.setDaemon(True)
            msg_thread.start()

            time.sleep(0.1)

            msg_thread = threading.Thread(target=the_tem_computer.compute_tem, args=(sk,))  # 温度计算线程
            msg_thread.setDaemon(True)
            msg_thread.start()
            msg_thread = threading.Thread(target=the_sender.send_request, args=(sk,))  # 发送修改请求线程
            msg_thread.setDaemon(True)
            msg_thread.start()
            self.child.child.pushButton_2.clicked.connect(self.stop_respon)
            self.child.child.pushButton_8.clicked.connect(self.temPlus_respon)
            self.child.child.pushButton_9.clicked.connect(self.temSub_respon)
            self.child.child.pushButton_3.clicked.connect(self.mode1_respon)
            self.child.child.pushButton_4.clicked.connect(self.mode2_respon)
            self.child.child.pushButton_5.clicked.connect(self.speed1_respon)
            self.child.child.pushButton_6.clicked.connect(self.speed2_respon)
            self.child.child.pushButton_7.clicked.connect(self.speed3_respon)

    def req(self, que):
        while True:
            if not que.empty():
                self.child.child.label_11.setText('请求已发送')
                time.sleep(1)
                self.child.child.label_11.setText('')
                que.queue.clear()
            time.sleep(0.1)

    def start_respon(self):
        self.msg = STARTMSG
        if self.msg == STARTMSG:
            global cold_low
            global cold_high
            global warm_low
            global warm_high
            global default_tem

            self.child.child.label_4.setText(str(room.room_tem))
            self.child.child.label_9.setText(str(int(room.ac_tem)))
            self.child.child.label_10.setText('制冷模式')
            self.child.child.label_14.setText('中风')
            self.msg = STARTMSG + ' ' + str(room.ac_mode) + ' ' + str(int(room.ac_tem)) + ' ' + str(room.ac_speed)
            socket_semaphore.acquire()
            sk.sendall(self.msg.encode('utf-8'))
            print("发出：", self.msg)
            socket_semaphore.release()
            room.isopen = True

            self.Mytimer()

    def Mytimer(self):
        timer = QTimer(self)
        timer.timeout.connect(self.update)
        timer.start(100)

    def update(self):
        self.child.child.label_4.setText(str(room.room_tem))

    def stop_respon(self):
        self.msg = STOPMSG
        socket_semaphore.acquire()
        sk.sendall(self.msg.encode('utf-8'))
        print("发出：", self.msg)
        socket_semaphore.release()
        room.ac_tem = default_tem
        room.ac_speed = MID

        self.child.child.pushButton.clicked.connect(self.start_respon)

    def temPlus_respon(self):
        global change_request_msg
        global change_flag
        global time_old
        self.msg = CHANGEMSG
        if room.ac_mode == WARM and room.ac_tem < warm_high:
            room.ac_tem += 1
            self.child.child.label_9.setText(str(int(room.ac_tem)))
            change_request_msg = CHANGEMSG + ' ' + str(room.ac_mode) + ' ' + str(int(room.ac_tem)) + ' ' + str(
                room.ac_speed)
            change_flag = 1
            time_old = time.time()
            room.request_state = WAITINGMSG
        if room.ac_mode == COLD and room.ac_tem < cold_high:
            room.ac_tem += 1
            self.child.child.label_9.setText(str(int(room.ac_tem)))
            change_request_msg = CHANGEMSG + ' ' + str(room.ac_mode) + ' ' + str(int(room.ac_tem)) + ' ' + str(
                room.ac_speed)
            change_flag = 1
            time_old = time.time()
            room.request_state = WAITINGMSG

    def temSub_respon(self):
        global change_request_msg
        global change_flag
        global time_old
        self.msg = CHANGEMSG
        if room.ac_mode == WARM and room.ac_tem > warm_low:
            room.ac_tem -= 1
            self.child.child.label_9.setText(str(int(room.ac_tem)))
            change_request_msg = CHANGEMSG + ' ' + str(room.ac_mode) + ' ' + str(int(room.ac_tem)) + ' ' + str(
                room.ac_speed)
            change_flag = 1
            time_old = time.time()
            room.request_state = WAITINGMSG
        if room.ac_mode == COLD and room.ac_tem > cold_low:
            room.ac_tem -= 1
            self.child.child.label_9.setText(str(int(room.ac_tem)))
            change_request_msg = CHANGEMSG + ' ' + str(room.ac_mode) + ' ' + str(int(room.ac_tem)) + ' ' + str(
                room.ac_speed)
            change_flag = 1
            time_old = time.time()
            room.request_state = WAITINGMSG

    def mode1_respon(self):
        global change_request_msg
        global change_flag
        global time_old
        self.msg = CHANGEMSG
        room.ac_mode = COLD
        self.child.child.label_10.setText('制冷模式')
        change_request_msg = CHANGEMSG + ' ' + str(room.ac_mode) + ' ' + str(int(room.ac_tem)) + ' ' + str(
            room.ac_speed)
        change_flag = 1
        time_old = time.time()
        room.request_state = WAITINGMSG

    def mode2_respon(self):
        global change_request_msg
        global change_flag
        global time_old
        self.msg = CHANGEMSG
        room.ac_mode = WARM
        self.child.child.label_10.setText('制热模式')
        change_request_msg = CHANGEMSG + ' ' + str(room.ac_mode) + ' ' + str(int(room.ac_tem)) + ' ' + str(
            room.ac_speed)
        change_flag = 1
        time_old = time.time()
        room.request_state = WAITINGMSG

    def speed1_respon(self):
        global change_request_msg
        global change_flag
        global time_old
        self.msg = CHANGEMSG
        room.ac_speed = LOW
        self.child.child.label_14.setText('低风')
        change_request_msg = CHANGEMSG + ' ' + str(room.ac_mode) + ' ' + str(int(room.ac_tem)) + ' ' + str(
            room.ac_speed)
        change_flag = 1
        time_old = time.time()
        room.request_state = WAITINGMSG

    def speed2_respon(self):
        global change_request_msg
        global change_flag
        global time_old
        self.msg = CHANGEMSG
        room.ac_speed = MID
        self.child.child.label_14.setText('中风')
        change_request_msg = CHANGEMSG + ' ' + str(room.ac_mode) + ' ' + str(int(room.ac_tem)) + ' ' + str(
            room.ac_speed)
        change_flag = 1
        time_old = time.time()
        room.request_state = WAITINGMSG

    def speed3_respon(self):
        global change_request_msg
        global change_flag
        global time_old
        self.msg = CHANGEMSG
        room.ac_speed = HIGH
        self.child.child.label_14.setText('高风')
        change_request_msg = CHANGEMSG + ' ' + str(room.ac_mode) + ' ' + str(int(room.ac_tem)) + ' ' + str(
            room.ac_speed)
        change_flag = 1
        time_old = time.time()
        room.request_state = WAITINGMSG


class childWindow(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        self.child = Ui_Dialog()
        self.child.setupUi(self)


if __name__ == '__main__':
    ADDRESS = ('127.0.0.1', 8009)
    BUFSIZE = 1024
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sk.connect(ADDRESS)

    room = Room(None, None, None, None, None)
    change_request_msg = "hi"
    cold_low = 18
    cold_high = 26
    warm_low = 26
    warm_high = 30

    default_tem = 26
    room_default_tem = 26
    time_old = time.time()
    change_flag = 0  # 有无修改请求
    arrive_flag = 0
    threadLock = threading.Lock()
    socket_semaphore = threading.Semaphore(1)
    threads = []

    app = QApplication(sys.argv)
    w = parentWindow()
    w.show()
    sys.exit(app.exec_())
