import socket
import threading

ADDRESS = ('127.0.0.1', 8009)
BUFSIZE = 1024
sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sk.connect(ADDRESS)


def message_listen(sk):
    while True:
        feedback = sk.recv(BUFSIZE)
        print(feedback.decode('utf-8'))


print("please log in")
username = input("username:")
passwd = input("password:")

if username != '' and passwd != '':
    msg = username + ' ' + passwd
    sk.sendall(msg.encode('utf-8'))
    feedback = sk.recv(BUFSIZE).decode('utf-8')
    print(feedback)
    if feedback == username + "登陆成功":
        msg_thread = threading.Thread(target=message_listen, args=(sk,))
        msg_thread.setDaemon(True)
        msg_thread.start()
        while True:
            msg = input().strip()
            if len(msg) == 0:
                break
            sk.sendall(msg.encode('utf-8'))
sk.close()
