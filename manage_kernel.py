import socket

ADDRESS = ('127.0.0.1', 8009)
BUFSIZE = 1024
sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

sk.connect(ADDRESS)

print("please log in")
username = input("username:")
passwd = input("password:")

if username != '' and passwd != '':
    msg = username + ',' + passwd
    sk.sendall(msg.encode('utf-8'))
    while True:
        feedback = sk.recv(BUFSIZE)
        print(feedback.decode('utf-8'))

sk.close()
