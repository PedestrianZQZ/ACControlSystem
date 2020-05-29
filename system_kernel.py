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

RUNNINGMSG = '1'  # 房间信令
WAITINGMSG = '2'

SUCCESSMSG = '1'  # 通用信令
FAILMSG = '0'


g_conn_pool_dict = {}  # 连接池
g_socket_server = None  # socket对象
staff_dict = {'0401': '0', '0402': '0', '0403': '0', '0404': '0', '1': '123456', '2': '123456', '3': '123456'}  # 工作人员信息,1开头表示服务员，2开头表示管理员，3开头表示经理
spare_room_list = ['0401', '0402', '0403', '0404', '0405', '0406', '0407', '0408', '0409', '0410']
room_dict = {}

ac = None  # 空调系统对象

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


def find_request_by_id(id, queue):
    for index, item in enumerate(queue):
        if item.id == id:
            return index
    return FAILMSG

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

    def check_out(self):
        self.isopen = False
        self.id = None
        self.room_tem = None
        self.set_tem = None
        self.set_speed = None

    # def get_ac_info(self):
    #     tem = self.ac_tem
    #     speed = self.ac_speed
    #     mode = self.ac_mode
    #     return tem, speed, mode

    def set_room_info(self, room_tem, ac_tem, ac_speed, ac_mode):
        self.room_tem = room_tem
        self.ac_tem = ac_tem
        self.ac_speed = ac_speed
        self.ac_mode = ac_mode




class Scheduler:
    wait_queue = []
    serve_queue = []
    pause_queue = []
    wait_time_list = []
    serve_time_list = []
    protected_list = []
    max_serve_num = 3
    max_wait_time = 0
    lock = None

    def __init__(self, max_serve_num, max_wait_time):
        self.max_serve_num = max_serve_num
        self.max_wait_time = max_wait_time

        self.lock = threading.RLock()

        thread = threading.Thread(target=self.schedule, args=(6,))
        thread.setDaemon(True)
        thread.start()
        return

    def add_request(self, request):
        self.lock.acquire()
        isok = False
        try:
            result = find_request_by_id(request.id, self.serve_queue)
            if result != FAILMSG:
                self.serve_queue.remove(self.serve_queue[result])
            result = find_request_by_id(request.id, self.wait_queue)
            if result != FAILMSG:
                self.wait_queue.remove(self.wait_queue[result])
            result = find_request_by_id(request.id, self.pause_queue)
            if result != FAILMSG:
                self.pause_queue.remove(self.pause_queue[result])

            if len(self.serve_queue) < int(self.max_serve_num):  # 如果服务队列有空位，直接加
                self.serve_queue.append(request)
                self.serve_time_list.append(0)
                client = g_conn_pool_dict[request.id]
                client.sendall(RUNNINGMSG.encode('utf-8'))
                room_dict[request.id].request_state = 'running'
            else:  # 如果服务队列没空位，选择性的加
                if request.speed == HIGH:  # 如果是高风
                    for item in self.serve_queue:
                        if item.speed != HIGH:  # 只要不是高风就换出来
                            self.swap_out(item.id)
                            self.serve_queue.append(request)
                            self.serve_time_list.append(0)
                            client = g_conn_pool_dict[request.id]
                            client.sendall(RUNNINGMSG.encode('utf-8'))
                            room_dict[request.id].request_state = 'running'
                            isok = True
                            break
                    if not isok:
                        self.wait_queue.append(request)  # 全是高风就加到等待队列等着
                        self.wait_time_list.append(0)
                        client = g_conn_pool_dict[request.id]
                        client.sendall(WAITINGMSG.encode('utf-8'))
                        room_dict[request.id].request_state = 'waiting'
                elif request.speed == MID:  # 如果是中风
                    for item in self.serve_queue:
                        if item.speed == LOW:  # 只能换低风
                            self.swap_out(item.id)
                            self.serve_queue.append(request)
                            self.serve_time_list.append(0)
                            client = g_conn_pool_dict[request.id]
                            client.sendall(RUNNINGMSG.encode('utf-8'))
                            room_dict[request.id].request_state = 'running'
                            isok = True
                            break
                    if not isok:
                        self.wait_queue.append(request)  # 没有低风就加到等待队列等着
                        self.wait_time_list.append(0)
                        client = g_conn_pool_dict[request.id]
                        client.sendall(WAITINGMSG.encode('utf-8'))
                        room_dict[request.id].request_state = 'waiting'
                elif request.speed == LOW:  # 如果是低风
                    self.wait_queue.append(request)  # 直接进入等待队列
                    self.wait_time_list.append(0)
                    client = g_conn_pool_dict[request.id]
                    client.sendall(WAITINGMSG.encode('utf-8'))
                    room_dict[request.id].request_state = 'waiting'

        finally:
            self.lock.release()

    def del_request(self, id):
        self.lock.acquire()
        try:
            result = find_request_by_id(id, self.serve_queue)
            if result == FAILMSG:
                result = find_request_by_id(id, self.wait_queue)
                if result == FAILMSG:
                    result = find_request_by_id(id, self.pause_queue)
                    if result == FAILMSG:
                        return False
                    else:
                        self.pause_queue.remove(self.pause_queue[result])
                else:
                    self.wait_queue.remove(self.serve_queue[result])
                    self.wait_time_list.remove(self.serve_time_list[result])
            else:
                self.serve_queue.remove(self.serve_queue[result])
                self.serve_time_list.remove(self.serve_time_list[result])
        finally:
            self.lock.release()
        return True

    def swap_in(self, id):
        self.lock.acquire()
        try:
            result = find_request_by_id(id, self.wait_queue)
            self.serve_queue.append(self.wait_queue[result])
            self.serve_time_list.append(0)
            self.wait_queue.remove(self.serve_queue[result])
            self.wait_time_list.remove(self.serve_time_list[result])
            client = g_conn_pool_dict[id]
            client.sendall(RUNNINGMSG.encode('utf-8'))
            room_dict[id].request_state = 'running'
        finally:
            self.lock.release()

    def swap_out(self, id):
        self.lock.acquire()
        try:
            result = find_request_by_id(id, self.serve_queue)
            self.wait_queue.append(self.serve_queue[result])
            self.wait_time_list.append(0)
            self.serve_queue.remove(self.serve_queue[result])
            self.serve_time_list.remove(self.serve_time_list[result])
            client = g_conn_pool_dict[id]
            client.sendall(WAITINGMSG.encode('utf-8'))
            room_dict[id].request_state = 'waiting'
        finally:
            self.lock.release()

    def select_request(self):
        result = self.wait_queue[0]
        wait_time = 0
        for index, item in enumerate(self.wait_queue):
            if item.speed > result.speed:  # 挑风速大的
                result = item
                wait_time = self.wait_time_list[index]
            elif item.speed == result.speed:  # 风速相同挑等待时间长的
                if self.wait_time_list[index] > wait_time:
                    result = item
                    wait_time = self.wait_time_list[index]
        return result.id

    def schedule(self, num):
        is_get_same = False
        while True:
            self.lock.acquire()
            try:
                while len(self.wait_queue) != 0 and len(self.serve_queue) < self.max_serve_num:  # 首先处理服务队列不满的情况
                    result = self.select_request()
                    self.swap_in(result)
                for index1, time1 in enumerate(self.wait_time_list):  # 接着处理到等待时间的请求
                    if time1 >= self.max_wait_time:
                        target_request = self.wait_queue[index1]
                        serve_time = -1  # 存疑

                        for index2, request in enumerate(self.serve_queue):
                            if request.speed < self.wait_queue[index1].speed:  # 如果服务队列中有优先级低的，直接替换
                                self.swap_out(request.id)
                                self.swap_in(self.wait_queue[index1].id)
                                break
                            elif request.speed == self.wait_queue[index1].speed and \
                                    self.serve_time_list[index2] > serve_time:  # 否则找服务时间最长同等级替换的替换
                                target_request = request
                                serve_time = self.serve_time_list[index2]
                                is_get_same = True

                        if is_get_same:  # 真正进行替换
                            self.swap_out(target_request.id)
                            self.swap_in(self.wait_queue[index1].id)

                for item in self.wait_time_list:  # 系统时钟更新
                    item = item + 1
                for item in self.serve_time_list:
                    item = item + 1
            finally:
                self.lock.release()
            time.sleep(5)

    def on_pause(self, id):
        self.lock.acquire()
        try:
            index = find_request_by_id(id, self.serve_queue)
            if index == FAILMSG:
                index = find_request_by_id(id, self.wait_queue)
            request = self.serve_queue[index]
            self.pause_queue.append(request)
            self.serve_queue.remove(self.serve_queue[index])
            self.serve_time_list.remove(self.serve_time_list[index])
            client = g_conn_pool_dict[id]
            client.sendall("ac pausing!".encode('utf-8'))
            room_dict[id].request_state = 'pausing'
        finally:
            self.lock.release()

    def on_resume(self, id):
        self.lock.acquire()
        isok = False
        try:
            index = find_request_by_id(id, self.pause_queue)
            request1 = self.pause_queue[index]

            if len(self.serve_queue) < self.max_serve_num:
                self.serve_queue.append(request1)
                self.serve_time_list.append(0)
            else:
                for index2, request in enumerate(self.serve_queue):
                    if request.speed < request1.speed:  # 如果服务队列中有优先级低的，直接替换
                        self.swap_out(request.id)
                        self.serve_queue.append(request1)
                        self.serve_time_list.append(0)
                        isok = True
                        client = g_conn_pool_dict[id]
                        client.sendall("ac resuming!".encode('utf-8'))
                        room_dict[id].request_state = 'running'
                        break

                if not isok:  # 如果没有优先级更低的，进入等待队列
                    self.wait_queue.append(request1)
                    self.wait_time_list.append(0)
                    client = g_conn_pool_dict[id]
                    client.sendall(WAITINGMSG.encode('utf-8'))
                    room_dict[id].request_state = 'waiting'
        finally:
            self.lock.release()


class AcController:
    cold_low = 18  # 调温范围
    warm_high = 30
    default_tem = 25  # 空调启动时的默认温度，同时也作为室温
    mode = COLDWARM  # 当前空调系统支持的运行模式
    max_serve_num = 1
    max_wait_time = 0
    high_price = 3
    mid_price = 2
    low_price = 1
    isopen = False
    sc = None  # 调度器对象

    def set_range(self, cold_low, warm_high):
        self.cold_low = cold_low
        self.warm_high = warm_high

    def set_default_tem(self, tem):
        self.default_tem = tem

    def set_max_serve_num(self, num):
        self.max_serve_num = num

    def set_mode(self, mode):
        self.mode = mode

    def set_wait_time(self, wait_time):
        self.max_wait_time = wait_time

    def set_price(self, high, mid, low):
        self.high_price = high
        self.mid_price = mid
        self.low_price = low

    def power_on(self):
        self.sc = Scheduler(self.max_serve_num, self.max_wait_time)
        self.isopen = True
        self.init_rooms()

    def init_rooms(self):
        if self.mode == COLDWARM:
            mode = COLD
        else:
            mode = self.mode
        tem = ac.get_default_tem()
        room_dict['0401'] = Room('0401', tem, tem, MID, mode)
        room_dict['0402'] = Room('0402', tem, tem, MID, mode)
        room_dict['0403'] = Room('0403', tem, tem, MID, mode)
        room_dict['0404'] = Room('0404', tem, tem, MID, mode)
        room_dict['0405'] = Room('0405', tem, tem, MID, mode)
        room_dict['0406'] = Room('0406', tem, tem, MID, mode)
        room_dict['0407'] = Room('0407', tem, tem, MID, mode)
        room_dict['0408'] = Room('0408', tem, tem, MID, mode)
        room_dict['0409'] = Room('0409', tem, tem, MID, mode)
        room_dict['0410'] = Room('0410', tem, tem, MID, mode)

    def get_mode(self):
        return self.mode

    def get_default_tem(self):
        return self.default_tem

    def handle_request(self, request):
        print('handle_user_request')
        self.sc.add_request(request)

    def handle_pause(self, id):
        self.sc.on_pause(id)

    def handle_resume(self, id):
        self.sc.on_resume(id)

    def handle_stop(self, id):
        print('handle_stop')
        self.sc.del_request(id)

    def get_ac_info(self):
        return self.default_tem, self.cold_low, self.warm_high, self.mode


ac = AcController()


class UserController:
    client = None
    addr = None
    id = None

    def __init__(self, id, client, addr):
        self.client = client
        self.addr = addr
        self.id = id

    def handler(self):
        while True:
            self.client.sendall("user handler\ninput the hole command: 1.start, 2.stop, 3.pause, 4.resume, 5.update, 6.change, 7.init".encode("utf-8"))
            msg = self.client.recv(BUFSIZE).decode(encoding="utf8")
            print(self.addr, "客户端消息:", msg)
            if len(msg) == 0:
                self.client.close()
                g_conn_pool_dict.pop(self.id)
                print(self.addr, "下线了")
                break
            else:
                if msg == STARTMSG:
                    self.set_start()
                elif msg == STOPMSG:
                    self.set_stop()
                elif msg == PAUSEMSG:
                    self.set_pause()
                elif msg == RESUMEMSG:
                    self.set_resume()
                elif msg == UPDATEMSG:
                    self.set_update()
                elif msg == CHANGEMSG:
                    self.set_change()
                elif msg == USERINITMSG:
                    self.send_init()
        return

    def set_start(self):
        system_info = str(ac.default_tem) + ' ' + str(ac.cold_low) + ' ' + str(ac.warm_high) + ' ' + \
            str(ac.mode)
        self.client.sendall(system_info.encode("utf-8"))
        self.client.sendall(
            "user handler\ninput mode tem speed".encode("utf-8"))
        msg = self.client.recv(BUFSIZE).decode(encoding="utf8")
        print(self.addr, "客户端消息:", msg)
        info = msg.split(' ')
        request = Request(self.id, info[0], int(info[1]), int(info[2]))
        ac.handle_request(request)
        self.client.sendall(SUCCESSMSG.encode("utf-8"))

    def set_stop(self):
        ac.handle_stop(self.id)
        self.client.sendall(SUCCESSMSG.encode("utf-8"))

    def set_pause(self):
        ac.handle_pause(self.id)
        self.client.sendall(SUCCESSMSG.encode("utf-8"))

    def set_resume(self):
        ac.handle_resume(self.id)
        self.client.sendall(SUCCESSMSG.encode("utf-8"))

    def set_update(self):
        self.client.sendall(
            "user handler\ninput room_tem ac_tem ac_speed ac_mode".encode("utf-8"))
        msg = self.client.recv(BUFSIZE).decode(encoding="utf8")
        print(self.addr, "客户端消息:", msg)
        info = msg.split(' ')
        room_dict[self.id].set_room_info(float(info[0]), int(info[1]), int(info[2]), info[3])
        self.client.sendall(SUCCESSMSG.encode("utf-8"))

    def set_change(self):
        self.client.sendall(
            "user handler\ninput mode tem speed".encode("utf-8"))
        msg = self.client.recv(BUFSIZE).decode(encoding="utf8")
        print(self.addr, "客户端消息:", msg)
        info = msg.split(' ')
        request = Request(self.id, info[0], int(info[1]), int(info[2]))
        ac.handle_request(request)
        self.client.sendall(SUCCESSMSG.encode("utf-8"))

    def send_init(self):
        dt, cl, wh, m = ac.get_ac_info()
        msg = str(dt) + ' ' + str(cl) + ' ' + str(wh) + ' ' + str(m)
        self.client.sendall(msg.encode("utf-8"))

class AdminController:
    client = None
    addr = None
    id = None

    def __init__(self, id, client, addr):
        self.client = client
        self.addr = addr
        self.id = id

    def handler(self):
        while True:
            self.client.sendall("admin handler\nselect mode: 1.supervise, 2.init set, 3.power on".encode("utf-8"))
            msg = self.client.recv(BUFSIZE).decode(encoding="utf8")
            print(self.addr, "客户端消息:", msg)
            if len(msg) == 0:
                self.client.close()
                g_conn_pool_dict.pop(self.id)
                print(self.addr, "下线了")
                break
            else:
                if msg == SUPERVISEMSG:
                    self.supervise(self.client, self.addr)
                elif msg == INITSETMSG:
                    self.init_set(self.client, self.addr)
                elif msg == POWERONMSG:
                    self.power_on(self.client, self.addr)
        return

    def supervise(self, client, addr):
        q = queue.Queue()
        print("supervise mode")
        client.sendall("supervise mode, input whatever to exit".encode("utf-8"))
        thread = threading.Thread(target=self.listen_exit, args=(q,))
        thread.setDaemon(True)
        thread.start()
        while True:
            if not q.empty():
                break
            for key in room_dict.keys():
                info = key + ':' + str(room_dict[key].request_state)
                client.sendall(info.encode("utf-8"))
            for item in ac.sc.serve_queue:
                client.sendall(str(item.id).encode("utf-8"))
            time.sleep(5)

    def listen_exit(self, q):
        msg = self.client.recv(BUFSIZE).decode(encoding="utf8")
        print(self.addr, "客户端消息:", msg)
        q.put("exit")



    def init_set(self, client, addr):
        print("init_set")
        client.sendall("init_set, input cl wh".encode("utf-8"))
        msg = self.client.recv(BUFSIZE).decode(encoding="utf8").split(' ')
        ac.set_range(msg[0], msg[1])
        client.sendall("init_set, input default_tem".encode("utf-8"))
        msg = self.client.recv(BUFSIZE).decode(encoding="utf8").split(' ')
        ac.set_default_tem(msg[0])
        client.sendall("init_set, input max_serve_num".encode("utf-8"))
        msg = self.client.recv(BUFSIZE).decode(encoding="utf8").split(' ')
        ac.set_max_serve_num(msg[0])
        client.sendall("init_set, input mode, 1.coldonly, 2.warmonly, 3.coldwarm".encode("utf-8"))
        msg = self.client.recv(BUFSIZE).decode(encoding="utf8").split(' ')
        ac.set_mode(msg[0])
        client.sendall("init_set, input wait time".encode("utf-8"))
        msg = self.client.recv(BUFSIZE).decode(encoding="utf8").split(' ')
        ac.set_wait_time(int(msg[0]))
        client.sendall("init_set, input high price, mid price, low price".encode("utf-8"))
        msg = self.client.recv(BUFSIZE).decode(encoding="utf8").split(' ')
        ac.set_price(float(msg[0]), float(msg[1]), float(msg[2]))
        client.sendall(SUCCESSMSG.encode("utf-8"))
        return

    def power_on(self, client, addr):
        ac.power_on()
        client.sendall("system start!".encode("utf-8"))


class WaiterController:
    client = None
    addr = None
    id = None

    def __init__(self, id, client, addr):
        self.client = client
        self.addr = addr
        self.id = id

    def handler(self):
        while True:
            self.client.sendall("waiter handler\nselect mode: 1.check in, 2.check out, 3.refresh".encode("utf-8"))
            msg = self.client.recv(BUFSIZE).decode(encoding="utf8")
            print(self.addr, "客户端消息:", msg)
            if len(msg) == 0:
                self.client.close()
                g_conn_pool_dict.pop(self.id)
                print(self.addr, "下线了")
                break
            else:
                if msg == CHECKINMSG:
                    self.check_in(self.client, self.addr)
                elif msg == CHECKOUTMSG:
                    self.check_out(self.client, self.addr)
                elif msg == REFRESHMSG:
                    self.refresh(self.client, self.addr)
        return

    def check_in(self, client, addr):
        client.sendall("input target room id:".encode("utf-8"))
        msg = client.recv(BUFSIZE).decode(encoding="utf8")
        print(addr, "客户端消息:", msg)
        room_dict[msg].check_in(ac.default_tem)
        spare_room_list.remove(msg)
        client.sendall((msg + "check in success!").encode("utf-8"))

    def check_out(self, client, addr):
        client.sendall("input target room id:".encode("utf-8"))
        msg = client.recv(BUFSIZE).decode(encoding="utf8")
        print(addr, "客户端消息:", msg)
        room_dict[msg].check_out()
        spare_room_list.append(msg)
        client.sendall((msg + "check out success!").encode("utf-8"))

    def refresh(self, client, addr):
        str = ''
        for item in spare_room_list:
            str = str + ' ' + item
        client.sendall(("spare room:" + str).encode("utf-8"))


class ManagerController:
    id = None
    client = None
    addr = None

    def __init__(self, id, client, addr):
        self.client = client
        self.addr = addr
        self.id = id

    def handler(self):
        while True:
            self.client.sendall("manager handler\nselect mode: 1.get log".encode("utf-8"))
            msg = self.client.recv(BUFSIZE).decode(encoding="utf8")
            print(self.addr, "客户端消息:", msg)
            if len(msg) == 0:
                self.client.close()
                g_conn_pool_dict.pop(self.id)
                print(self.addr, "下线了")
                break
            else:
                if msg == GETLOGMSG:
                    self.getlog(self.client, self.addr)
        return

    def getlog(self, client, addr):
        self.client.sendall("input date: mm-dd".encode("utf-8"))
        msg = self.client.recv(BUFSIZE).decode(encoding="utf8")
        print(self.addr, "客户端消息:", msg)
        self.client.sendall(("daily log of %s output success" % msg).encode("utf-8"))


def init_socket():
    global g_socket_server
    g_socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    g_socket_server.bind(ADDRESS)
    g_socket_server.listen(5)
    print("系统内核已启动，等待前端连接...")


def accept_client():
    """
    接收新连接
    :return:
    """
    while True:
        client, addr = g_socket_server.accept()

        login_msg = client.recv(BUFSIZE).decode(encoding="utf8").split(" ")
        g_conn_pool_dict[login_msg[0]] = client
        passwd = staff_dict.get(login_msg[0], STAFF_NOT_EXIST)

        if passwd == STAFF_NOT_EXIST:
            client.sendall("账户不存在".encode('utf-8'))
        else:
            if passwd != login_msg[1]:
                client.sendall("用户名或密码错误".encode('utf-8'))
            else:
                client.sendall((login_msg[0] + "登陆成功").encode('utf-8'))
                thread = threading.Thread(target=message_handle, args=(client, addr, login_msg, passwd))
                thread.setDaemon(True)
                thread.start()


def message_handle(client, addr, login_msg, passwd):
    print('message_handle')
    account_kind = login_msg[0][0]  # 通过账号第一位标识是什么角色
    if account_kind == ADMIN:
        acontroller = AdminController(login_msg[0], client, addr)
        acontroller.handler()
    elif account_kind == USER:
        ucontroller = UserController(login_msg[0], client, addr)
        ucontroller.handler()
    elif account_kind == WAITER:
        wcontroller = WaiterController(login_msg[0], client, addr)
        wcontroller.handler()
    elif account_kind == MANAGER:
        mcontroller = ManagerController(login_msg[0], client, addr)
        mcontroller.handler()


if __name__ == '__main__':
    init_socket()

    thread = threading.Thread(target=accept_client())
    thread.setDaemon(True)
    thread.start()




