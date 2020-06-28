import threading
import socket
import time
import queue
import DBOperation
COLD = '1'  # 顾客请求空调设置参数
WARM = '2'
LOW = 1
MID = 2
HIGH = 3

COLDONLY = '1'  # 管理员空调运行模式设置
WARMONLY = '2'
COLDWARM = '3'

TIME_RATE = 5  # 5秒一个时钟周期
START_TIME = time.time()  #系统运行的开始时间
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

RUNNINGMSG = '8'  # 房间信令
WAITINGMSG = '9'

SUCCESSMSG = '1'  # 通用信令
FAILMSG = '0'


g_conn_pool_dict = {}  # 连接池
g_socket_server = None  # socket对象
spare_room_list = ['0401', '0402', '0403', '0404', '0405']
room_dict = {}

ac = None  # 空调系统对象

#将用户和密码从数据库存入字典staff_dict
def getStaff():
    sql = "select username, passwd from staff"
    DB_Log = DBOperation.IMapper()
    result = DB_Log.query(sql)
    staff_dict = dict()
    for x in result:
        user = x[0]
        pwd = x[1]
        staff_dict[user] = pwd
    DB_Log.DB.close_conn()
    return staff_dict
staff_dict = getStaff()

#获得该系统时间
def get_sys_time():
    t = int(START_TIME)
    now_time = int(time.time())
    span = (now_time - t) * 12 + t
    timeArray = time.localtime(span)
    sys_time = time.strftime("%Y-%m-%d %H:%M:%S", timeArray)
    return(str(sys_time))

bill_dict = dict()
class get_bill:
    def set_item(self,id):
        if id not in bill_dict.keys():
            bill_dict[id] = DBOperation.bill()

    def set_checkin_time(self,id,time):
        bill_dict[id].check_in_time = time

    def set_checkout_time(self,id,time):
        bill_dict[id].check_out_time = time

    def set_fee(self,id):
        # 获得总费用
        report_dict = DBOperation.get_replist().get_report()
        R = report_dict[id]
        bill_dict[id].cost = R.cost

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
        self.request_state = 'stopping'

    def check_in(self, tem):
        self.isopen = True
        self.ac_tem = tem
        self.ac_speed = MID

    def check_out(self):
        self.isopen = False
        self.id = None
        self.room_tem = None
        self.set_tem = None
        self.set_speed = None

    def set_room_info(self, room_tem, ac_tem, ac_speed, ac_mode):
        self.room_tem = room_tem
        self.ac_tem = ac_tem
        self.ac_speed = ac_speed
        self.ac_mode = ac_mode

    def get_room_tem(self):
        return self.room_tem

    def get_room_info(self):
        data = []
        data.append(self.isopen)
        data.append(self.request_state)
        data.append(self.room_tem)
        data.append(self.ac_mode)
        data.append(self.ac_tem)
        data.append(self.ac_speed)
        return data


class Scheduler:
    wait_queue = []
    serve_queue = []
    pause_queue = []
    wait_time_list = []
    serve_time_list = []
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
                self.serve_time_list.remove(self.serve_time_list[result])
            result = find_request_by_id(request.id, self.wait_queue)
            if result != FAILMSG:
                self.wait_queue.remove(self.wait_queue[result])
                self.wait_time_list.remove(self.wait_time_list[result])
            result = find_request_by_id(request.id, self.pause_queue)
            if result != FAILMSG:
                self.pause_queue.remove(self.pause_queue[result])

            if len(self.serve_queue) < int(self.max_serve_num) and len(self.wait_queue) == 0:  # 如果服务队列有空位，直接加
                self.serve_queue.append(request)
                self.serve_time_list.append(0)
                client = g_conn_pool_dict[request.id]
                client.sendall(RUNNINGMSG.encode('utf-8'))
                room_dict[request.id].request_state = 'running'
                isok = True
            else:  # 如果服务队列没空位，选择性的加
                if request.speed != LOW:  # 不是低风，存在直接进入运行队列的可能性
                    locate = self.select_lowest_request()
                    if self.serve_queue[locate].speed < request.speed:
                        self.swap_out(self.serve_queue[locate].id)
                        self.serve_queue.append(request)
                        self.serve_time_list.append(0)
                        client = g_conn_pool_dict[request.id]
                        client.sendall(RUNNINGMSG.encode('utf-8'))
                        room_dict[request.id].request_state = 'running'
                        isok = True
                    else:
                        self.wait_queue.append(request)  # 直接进入等待队列
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


            # 将结果写入数据库
            now_time = get_sys_time()
            if isok:
                sql = "insert into log values('" + now_time + "','" + request.id + "', 'running','" + str(
                    request.tem) + "','" + str(request.speed) + "')"
            else:
                 sql = "insert into log values('" + now_time + "','" + request.id + "', 'waiting','" + str(
                    request.tem) + "','" + str(request.speed) + "')"
            DB_Log = DBOperation.IMapper()
            DB_Log.update(sql)
            DB_Log.DB.close_conn()

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
                        client = g_conn_pool_dict[id]
                        client.sendall(STOPMSG.encode('utf-8'))
                        room_dict[id].request_state = 'stopping'
                else:
                    self.wait_queue.remove(self.wait_queue[result])
                    self.wait_time_list.remove(self.wait_time_list[result])
                    client = g_conn_pool_dict[id]
                    client.sendall(STOPMSG.encode('utf-8'))
                    room_dict[id].request_state = 'stopping'
            else:
                self.serve_queue.remove(self.serve_queue[result])
                self.serve_time_list.remove(self.serve_time_list[result])
                client = g_conn_pool_dict[id]
                client.sendall(STOPMSG.encode('utf-8'))
                room_dict[id].request_state = 'stopping'
        finally:
            self.lock.release()
        return True

    def swap_in(self, id):
        self.lock.acquire()
        try:
            # 写入数据库
            room = room_dict[id]
            now_time = get_sys_time()
            sql = "insert into log values('" + now_time + "','" + id + "', 'swap in','" + str(
                room.ac_tem) + "','" + str(
                room.ac_speed) + "')"
            DB_Log = DBOperation.IMapper()
            DB_Log.update(sql)
            DB_Log.DB.close_conn()

            result = find_request_by_id(id, self.wait_queue)
            self.serve_queue.append(self.wait_queue[result])
            self.serve_time_list.append(0)
            self.wait_queue.remove(self.wait_queue[result])
            self.wait_time_list.remove(self.wait_time_list[result])
            client = g_conn_pool_dict[id]
            client.sendall(RUNNINGMSG.encode('utf-8'))
            room_dict[id].request_state = 'running'
        finally:
            self.lock.release()

    def swap_out(self, id):
        self.lock.acquire()
        try:
            # 写入数据库
            room = room_dict[id]
            now_time = get_sys_time()
            sql = "insert into log values('" + now_time + "','" + id + "', 'swap out','" + str(
                room.ac_tem) + "','" + str(room.ac_speed) + "')"
            DB_Log = DBOperation.IMapper()
            DB_Log.update(sql)
            DB_Log.DB.close_conn()

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

    def select_best_request(self):
        result = self.wait_queue[0]
        wait_time = self.wait_time_list[0]
        for index, item in enumerate(self.wait_queue):
            if item.speed > result.speed:  # 挑风速大的
                result = item
                wait_time = self.wait_time_list[index]
            elif item.speed == result.speed:  # 风速相同挑等待时间长的
                if self.wait_time_list[index] > wait_time:
                    result = item
                    wait_time = self.wait_time_list[index]
        return result.id

    def select_lowest_request(self):
        result = self.serve_queue[0]
        locate = 0
        serve_time = 0
        for index, request in enumerate(self.serve_queue):
            if request.speed < result.speed:  # 挑风速最低的
                result = request
                locate = index
                serve_time = self.serve_time_list[index]
            elif request.speed == result.speed:  # 风速一样挑时间长的
                request_time = self.serve_time_list[index]
                if request_time > serve_time:
                    result = request
                    locate = index
                    serve_time = request_time
        return locate

    def schedule(self, num):
        i = 0
        while True:
            self.lock.acquire()
            try:
                while len(self.wait_queue) != 0 and len(self.serve_queue) < int(self.max_serve_num):  # 首先处理服务队列不满的情况
                    result = self.select_best_request()
                    self.swap_in(result)
                # 接着进行优先级调度
                for wrequest in self.wait_queue:
                    srequest = self.serve_queue[int(self.select_lowest_request())]
                    if wrequest.speed > srequest.speed:
                        self.swap_out(srequest.id)
                        self.swap_in(wrequest.id)

                for index1, time1 in enumerate(self.wait_time_list):  # 接着处理到等待时间的请求
                    if time1 >= self.max_wait_time:
                        target_request = self.wait_queue[index1]
                        locate = self.select_lowest_request()

                        if target_request.speed >= self.serve_queue[locate].speed:
                            self.swap_out(self.serve_queue[locate].id)
                            self.swap_in(target_request.id)

                for index, item in enumerate(self.wait_time_list):  # 系统时钟更新
                    self.wait_time_list[index] += 1
                for index, item in enumerate(self.serve_time_list):
                    self.serve_time_list[index] += 1
            finally:
                self.lock.release()

            print('-------------------------clock', i)
            i += 1
            time.sleep(TIME_RATE)

    def on_pause(self, id):
        self.lock.acquire()
        try:
            index = find_request_by_id(id, self.serve_queue)
            if index == FAILMSG:
                index = find_request_by_id(id, self.wait_queue)
                if index == FAILMSG:
                    pass
                else:
                    request = self.wait_queue[index]
                    self.pause_queue.append(request)
                    self.wait_queue.remove(self.wait_queue[index])
                    self.wait_time_list.remove(self.wait_time_list[index])
            else:
                request = self.serve_queue[index]
                self.pause_queue.append(request)
                self.serve_queue.remove(self.serve_queue[index])
                self.serve_time_list.remove(self.serve_time_list[index])
            client = g_conn_pool_dict[id]
            client.sendall(PAUSEMSG.encode('utf-8'))
            room_dict[id].request_state = 'pausing'
        finally:
            self.lock.release()

    def on_resume(self, id):
        self.lock.acquire()
        isok = False
        flag = 0
        try:
            index = find_request_by_id(id, self.pause_queue)
            request1 = self.pause_queue[int(index)]

            if len(self.serve_queue) < int(self.max_serve_num):  # 如果服务队列不满，则直接加入服务队列
                self.serve_queue.append(request1)
                self.serve_time_list.append(0)
                client = g_conn_pool_dict[id]
                client.sendall(RUNNINGMSG.encode('utf-8'))
                room_dict[id].request_state = 'running'
                flag = 1
            else:
                locate = self.select_lowest_request()  # 如果队列满，欺负最弱的
                if request1.speed > self.serve_queue[locate].speed:
                    self.swap_out(self.serve_queue[locate].id)
                    self.serve_queue.append(request1)
                    self.serve_time_list.append(0)
                    client = g_conn_pool_dict[id]
                    client.sendall(RUNNINGMSG.encode('utf-8'))
                    room_dict[id].request_state = 'running'
                else:  # 如果没有优先级更低的，进入等待队列
                    self.wait_queue.append(request1)
                    self.wait_time_list.append(0)
                    client = g_conn_pool_dict[id]
                    client.sendall(WAITINGMSG.encode('utf-8'))
                    room_dict[id].request_state = 'waiting'
                    flag = 2
            self.pause_queue.remove(request1)
            # 将结果写入数据库
            now_time = get_sys_time()
            # sql = ''
            if flag == 1:
                sql = "insert into log values('" + now_time + "','" + id + "', 'running','" + str(
                    request1.tem) + "','" + str(request1.speed) + "')"
                DB_Log = DBOperation.IMapper()
                DB_Log.update(sql)
                DB_Log.DB.close_conn()
            elif flag == 2:
                sql = "insert into log values('" + now_time + "','" + id + "', 'waiting','" + str(
                    request1.tem) + "','" + str(request1.speed) + "')"
                DB_Log = DBOperation.IMapper()
                DB_Log.update(sql)
                DB_Log.DB.close_conn()
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
        room_dict['0401'] = Room('0401', 32, tem, MID, mode)
        room_dict['0402'] = Room('0402', 28, tem, MID, mode)
        room_dict['0403'] = Room('0403', 30, tem, MID, mode)
        room_dict['0404'] = Room('0404', 29, tem, MID, mode)
        room_dict['0405'] = Room('0405', 35, tem, MID, mode)

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
        if room_dict[self.id].isopen:
            while True:
                # self.client.sendall("user handler\ninput the whole command: 1.start, 2.stop, 3.pause, 4.resume, 5.update, 6.change, 7.init".encode("utf-8"))
                msg = self.client.recv(BUFSIZE).decode(encoding="utf8").split(' ')
                print(self.addr, "客户端消息:", msg)
                if len(msg) == 0:
                    self.client.close()
                    g_conn_pool_dict.pop(self.id)
                    print(self.addr, "下线了")
                    break
                else:
                    if msg[0] == STARTMSG:
                        self.set_start(msg[1:])
                    elif msg[0] == STOPMSG:
                        self.set_stop()
                    elif msg[0] == PAUSEMSG:
                        self.set_pause()
                    elif msg[0] == RESUMEMSG:
                        self.set_resume()
                    elif msg[0] == UPDATEMSG:
                        self.set_update(msg[1:])
                    elif msg[0] == CHANGEMSG:
                        self.set_change(msg[1:])
                    elif msg[0] == USERINITMSG:
                        self.send_info()
        else:
            self.client.sendall('room not open!'.encode('utf-8'))

    def set_start(self, msg):
        print(self.addr, "客户端消息:", msg)
        info = msg
        room_tem = room_dict[self.id].get_room_tem()
        room_dict[self.id].set_room_info(room_tem, int(info[1]), int(info[2]), info[0])
        request = Request(self.id, info[0], int(info[1]), int(info[2]))
        ac.handle_request(request)
        # self.client.sendall(SUCCESSMSG.encode("utf-8"))

    def set_stop(self):
        ac.handle_stop(self.id)
        room = room_dict[self.id]
        tem = room.ac_tem
        speed = room.ac_speed
        now_time = get_sys_time()
        sql = "insert into log values('" + now_time + "','" + self.id + "', 'stop','" + str(tem) + "','" + str(
            speed) + "')"
        DB_Log = DBOperation.IMapper()
        DB_Log.update(sql)
        DB_Log.DB.close_conn()

    def set_pause(self):
        ac.handle_pause(self.id)
        room = room_dict[self.id]
        tem = room.ac_tem
        speed = room.ac_speed
        now_time = get_sys_time()
        sql = "insert into log values('" + now_time + "','" + self.id + "','pausing','" + str(tem) + "','" + str(
            speed) + "')"
        DB_Log = DBOperation.IMapper()
        DB_Log.update(sql)
        DB_Log.DB.close_conn()

    def set_resume(self):
        ac.handle_resume(self.id)
        # self.client.sendall(SUCCESSMSG.encode("utf-8"))

    def set_update(self, msg):
        print(self.addr, "客户端消息:", msg)
        info = msg
        room_dict[self.id].set_room_info(float(info[0]), int(info[1]), int(info[2]), info[3])
        self.client.sendall(UPDATEMSG.encode("utf-8"))


    def set_change(self, msg):
        print(self.addr, "客户端消息:", msg)
        info = msg
        request = Request(self.id, info[0], int(info[1]), int(info[2]))
        room_tem = room_dict[self.id].get_room_tem()
        room_dict[self.id].set_room_info(room_tem, int(info[1]), int(info[2]), info[0])
        ac.handle_request(request)
        # self.client.sendall(SUCCESSMSG.encode("utf-8"))

    def send_info(self):
        room_tem = room_dict[self.id].get_room_tem()
        system_info = str(ac.default_tem) + ' ' + str(ac.cold_low) + ' ' + str(ac.warm_high) + ' ' + \
                      str(ac.mode) + ' ' + str(room_tem)
        self.client.sendall(system_info.encode("utf-8"))


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
            # self.client.sendall("admin handler\ninput whole command: \
            # 1.supervise, 2.init set, 3.power on".encode("utf-8"))
            msg = self.client.recv(BUFSIZE).decode(encoding="utf8").split(' ')
            print(self.addr, "客户端消息:", msg)
            if len(msg) == 0:
                self.client.close()
                g_conn_pool_dict.pop(self.id)
                print(self.addr, "下线了")
                break
            else:
                if msg[0] == SUPERVISEMSG:
                    self.supervise(self.client, self.addr)
                elif msg[0] == INITSETMSG:
                    self.init_set(self.client, self.addr, msg[1:])
                elif msg[0] == POWERONMSG:
                    self.power_on(self.client, self.addr)
        return

    def supervise(self, client, addr):
        q = queue.Queue()
        print("supervise mode")
        # client.sendall("supervise mode, input whatever to exit".encode("utf-8"))
        thread = threading.Thread(target=self.listen_exit, args=(q,))
        thread.setDaemon(True)
        thread.start()
        while True:
            if not q.empty():
                break
            info = ''
            for key in room_dict.keys():
                data = room_dict[key].get_room_info()
                # isopen + request_state + room_tem + ac_mode + ac_tem + ac_speed
                info = info + key + ' ' + str(data[0]) + ' ' + str(data[1]) + ' ' \
                       + str(data[2]) + ' ' + str(data[3]) + ' ' + str(data[4]) + ' ' + str(data[5]) + ' '
            client.sendall(info.encode("utf-8"))
            # for item in ac.sc.serve_queue:
            #     client.sendall(str(item.id).encode("utf-8"))
            time.sleep(TIME_RATE)

    def listen_exit(self, q):
        msg = self.client.recv(BUFSIZE).decode(encoding="utf8")
        print(self.addr, "客户端消息:", msg)
        q.put("exit")



    def init_set(self, client, addr, msg):
        print("init_set")
        # client.sendall("init_set, input cl wh".encode("utf-8"))
        # msg = self.client.recv(BUFSIZE).decode(encoding="utf8").split(' ')
        ac.set_range(msg[0], msg[1])
        # client.sendall("init_set, input default_tem".encode("utf-8"))
        # msg = self.client.recv(BUFSIZE).decode(encoding="utf8").split(' ')
        ac.set_default_tem(msg[2])
        # client.sendall("init_set, input max_serve_num".encode("utf-8"))
        # msg = self.client.recv(BUFSIZE).decode(encoding="utf8").split(' ')
        ac.set_max_serve_num(msg[3])
        # client.sendall("init_set, input mode, 1.coldonly, 2.warmonly, 3.coldwarm".encode("utf-8"))
        # msg = self.client.recv(BUFSIZE).decode(encoding="utf8").split(' ')
        ac.set_mode(msg[4])
        # client.sendall("init_set, input wait time".encode("utf-8"))
        # msg = self.client.recv(BUFSIZE).decode(encoding="utf8").split(' ')
        ac.set_wait_time(int(msg[5]))
        # client.sendall("init_set, input high price, mid price, low price".encode("utf-8"))
        # msg = self.client.recv(BUFSIZE).decode(encoding="utf8").split(' ')
        ac.set_price(float(msg[6]), float(msg[7]), float(msg[8]))
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
            # self.client.sendall("waiter handler\ninput whole command: 1.check in, 2.check out, 3.refresh".encode("utf-8"))
            msg = self.client.recv(BUFSIZE).decode(encoding="utf8").split(' ')
            print(self.addr, "客户端消息1:", msg)
            if len(msg) == 0:
                self.client.close()
                g_conn_pool_dict.pop(self.id)
                print(self.addr, "下线了")
                break
            else:
                if msg[0] == CHECKINMSG:
                    self.check_in(self.client, self.addr, msg[1:])
                elif msg[0] == CHECKOUTMSG:
                    self.check_out(self.client, self.addr, msg[1:])
                elif msg[0] == REFRESHMSG:
                    self.refresh(self.client, self.addr)
        return

    def check_in(self, client, addr, msg):
        # client.sendall("input target room id:".encode("utf-8"))
        # msg = client.recv(BUFSIZE).decode(encoding="utf8")
        print(addr, "客户端消息:", msg)
        room_dict[str(msg[0])].check_in(ac.default_tem)
        spare_room_list.remove(str(msg[0]))
        client.sendall((str(msg[0]) + "check in success!").encode("utf-8"))
        now_time = get_sys_time()
        Bill = get_bill()
        Bill.set_item(str(msg[0]))
        Bill.set_checkin_time(str(msg[0]), now_time)

    def check_out(self, client, addr, msg):
        # client.sendall("input target room id:".encode("utf-8"))
        # msg = client.recv(BUFSIZE).decode(encoding="utf8")
        print(addr, "客户端消息2:", msg)
        room_dict[str(msg[0])].check_out()
        spare_room_list.append(str(msg[0]))
        spare_room_list.sort()
        client.sendall((str(msg[0]) + "check out success!").encode("utf-8"))
        now_time = get_sys_time()
        Bill = get_bill()
        Bill.set_item(str(msg[0]))
        Bill.set_checkout_time(str(msg[0]), now_time)
        Bill.set_fee(str(msg[0]))
        room_bill = bill_dict[str(msg[0])]  # 入店时间、出店时间、花费
        room_detail_list = DBOperation.get_replist().get_roomlist(str(msg[0]))  # dbo detailist
        msg = str(msg[0]) + ',' + str(room_bill.check_in_time) + '^' + str(room_bill.check_out_time) + \
            '^' + str(room_bill.cost) + ','
        for index, item in enumerate(room_detail_list):
            if index != len(room_detail_list) - 1:
                msg = msg + str(item.start.split(' ')[1]) + '^' + str(item.end.split(' ')[1]) + '^' + str(item.duration) + '^' + \
                    str(item.speed) + '^' + str(item.rate) + '^' + str(item.cost) + '|'
            else:
                msg = msg + str(item.start.split(' ')[1]) + '^' + str(item.end.split(' ')[1]) + '^' + str(item.duration) + '^' + \
                      str(item.speed) + '^' + str(item.rate) + '^' + str(item.cost)
        print(msg)
        signal = client.recv(BUFSIZE).decode(encoding="utf8").split(' ')
        print(signal)
        if signal[0] == BILLMSG:
            client.sendall(msg.encode("utf-8"))


        '''for x in bill_dict.keys():
            a = bill_dict[x]
            print(a.check_in_time + ' ' + a.check_out_time + ' ' + str(a.cost))'''

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
            # self.client.sendall("manager handler\nselect mode: 1.get log".encode("utf-8"))
            msg = self.client.recv(BUFSIZE).decode(encoding="utf8").split(' ')
            print(self.addr, "客户端消息:", msg)
            if len(msg) == 0:
                self.client.close()
                g_conn_pool_dict.pop(self.id)
                print(self.addr, "下线了")
                break
            else:
                if msg[0] == GETLOGMSG:
                    self.get_log(self.client, self.addr, msg[1:])
        return

    def get_log(self, client, addr, msg):
        # self.client.sendall("input date: mm-dd".encode("utf-8"))
        # msg = self.client.recv(BUFSIZE).decode(encoding="utf8")
        print(self.addr, "客户端消息:", msg[0])
        f = DBOperation.get_replist().get_file_report()
        print(f)
        if f == 'success':
            self.client.sendall(("daily log of %s output success" % msg[0]).encode("utf-8"))


class Communicate:

    def init_socket(self):
        global g_socket_server
        g_socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        g_socket_server.bind(ADDRESS)
        g_socket_server.listen(5)
        print("系统内核已启动，等待前端连接...")


    def accept_client(self):
        """
        接收新连接
        :return:
        """
        while True:
            client, addr = g_socket_server.accept()
            global g_conn_pool_dict
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
                    thread = threading.Thread(target=self.message_handle, args=(client, addr, login_msg, passwd))
                    thread.setDaemon(True)
                    thread.start()


    def message_handle(self, client, addr, login_msg, passwd):
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
    c = Communicate()
    c.init_socket()

    thread = threading.Thread(target=c.accept_client())
    thread.setDaemon(True)
    thread.start()
