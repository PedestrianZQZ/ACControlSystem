import threading
import socket

MAX_QUEUE_LENGTH = 5  # 最大同时服务的请求数
DEFAULT_TEM = 26  # 默认温度26
DEFAULT_SPEED = 2  # 默认中风
TIME_RATE = 5  # 5秒一个时钟周期
ADDRESS = ('127.0.0.1', 8009)  # socket接口
BUFSIZE: int = 1024  # socket消息缓冲区大小
STAFF_NOT_EXIST = "ERROR"
USER = '0'
WAITER = '1'
ADMIN = '2'
MANAGER = '3'
g_conn_pool = []  # 连接池
g_socket_server = None  # socket对象
staff = {'1': '123456', '2': '123456', '3': '123456'}  # 工作人员信息,1开头表示服务员，2开头表示管理员，3开头表示经理


class Request:
    """
    params
    id: 房间号
    tem: 温度
    speed: 风速
    """
    id = 0
    tem = 0.0
    speed = 0

    def __init__(self, id, tem, speed):
        self.id = id
        self.tem = tem
        self.speed = speed


class AdminController:
    client = None
    addr = None

    def __init__(self, client, addr):
        self.client = client
        self.addr = addr

    def handler(self):
        self.client.sendall("admin handler".encode("utf-8"))
        return

    def supervise(self):
        print("supervise mode")

    def modify(self):
        print("modify mode")


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
        g_conn_pool.append(client)

        login_msg = client.recv(BUFSIZE).decode(encoding="utf8").split(",")
        passwd = staff.get(login_msg[0], STAFF_NOT_EXIST)

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
    account_kind = login_msg[0][0]  # 通过账号第一位标识是什么角色

    if account_kind == ADMIN:
        acontroller = AdminController(client, addr)
        acontroller.handler()
            # while True:
            #     msg = client.recv(BUFSIZE).decode(encoding="utf8")
            #     print(addr, "客户端消息:", msg)
            #     if len(msg) == 0:
            #         client.close()
            #         g_conn_pool.remove(client)
            #         print(addr, "下线了")
            #         break


if __name__ == '__main__':
    init_socket()

    thread = threading.Thread(target=accept_client())
    thread.setDaemon(True)
    thread.start()

    while True:
        cmd = input("""--------------------------
    输入1:查看当前在线人数
    输入2:给指定客户端发送消息
    输入3:关闭服务端
    """)
        if cmd == '1':
            print("--------------------------")
            print("当前在线人数：", len(g_conn_pool))
        elif cmd == '2':
            print("--------------------------")
            index, msg = input("请输入“索引,消息”的形式：").split(",")
            g_conn_pool[int(index)].sendall(msg.encode(encoding='utf8'))
        elif cmd == '3':
            exit()



