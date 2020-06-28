import pymssql
import time
import csv

USER = "sa"   #连接数据库用户名
PWD = "123456"   #连接数据库密码
DATABASE_NAME = "AirCondition"   #数据库名字

class IMapper:

    def __init__(self):
        self.DB = DBConnection()

    # 插入，修改，删除
    def update(self,sql):
        conn = self.DB.getConnection()
        cur = self.DB.getCursor()
        cur.execute(sql)
        flag = conn.commit()
        return flag
    #查询
    def query(self, sql):
        cur = self.DB.getCursor()
        cur.execute(sql)
        result = cur.fetchall()
        return result

class DBConnection:
    conn = None
    cursor = None
    def __init__(self):
        self.conn = pymssql.connect('(local)', USER, PWD, DATABASE_NAME)  # 建立连接
        self.cursor = self.conn.cursor()

    def getConnection(self):
        return self.conn
    def getCursor(self):
        return self.cursor

    def close_conn(self):
        self.cursor.close()
        self.conn.close()

class report:
    #日报表
    def __init__(self):
        self.open = "0"
        self.duration = 0
        self.cost = 0
        self.dispatch = "0"
        self.count = 0
        self.temp = 0
        self.speed = 0

    def toString(self):
        str1 = self.open+'            '+str(self.duration)+'    '+str(self.cost)+'  '
        str1 = str1+ self.dispatch+'            '+str(self.count)+'         '+str(self.temp)+'            '+str(self.speed)
        return str1

room_dict = {"0401":0,"0402":1,"0403":0,"0404":1,"0405":1}
bill_dict = dict()
class detailed_list:
    def __init__(self):
        self.start = '0'  # 开始时间
        self.end = '0'  # 结束时间
        self.duration = '0'  # 持续时间
        self.speed = '中'  # 风速
        self.rate = '0.5'  # 费率
        self.cost = '0'  # 花费

    def print_list(self):
        print(self.start + " "+ self.end+" "+str(self.duration)+" "+str(self.speed)+" "+str(self.rate)+" "+str(self.cost))

class bill:
    def __init__(self):
        self.check_in_time = ''
        self.check_out_time = ''
        self.cost = 0

class get_replist:
    def get_alllist(self):
        list_dict = dict()
        for x in room_dict.keys():
            list_dict[x] = get_replist().get_roomlist(x)
        return list_dict

    def get_roomlist(self, ID):
        sum_list = []
        sql = "select time, operation, speed from log where roomID = '" + ID + "' order by time"
        DB_log = IMapper()
        result = DB_log.query(sql)
        if result:
            time_last = result[0][0]
            state_last = result[0][1]
            speed_last = result[0][2]
            for x in result:
                delist = detailed_list()
                time = x[0]
                state = x[1]
                speed = x[2]
                if time == time_last :
                    time_last = time
                    state_last = state
                    speed_last = speed
                    continue
                if state_last == 'stop' or state_last == 'pausing' or state_last == 'swap out' or state_last == 'waiting':
                    time_last = time
                    state_last = state
                    speed_last = speed
                    continue
                span = self.geTimeSpan(time, time_last)
                if speed_last == '3':
                    rate = 1
                elif speed_last == '2':
                    rate = 0.5
                else:
                    rate = 0.3
                delist.start = time_last
                delist.end = time
                delist.duration = span
                delist.speed = speed_last
                delist.rate = rate
                delist.cost = span*rate
                sum_list.append(delist)
                time_last = time
                state_last = state
                speed_last = speed
        return sum_list

    def get_report(self):
        DB_log = IMapper()
        rep_dict = dict()
        for ID in room_dict.keys():
            # 获得开关次数
            rep = report()
            sql = "select count(*) from log where roomID = '" + ID + "' and operation = 'stop'"
            result = DB_log.query(sql)
            rep.open = str(result[0][0])

            #获得总时长,总费用,详单数,调温次数，调风次数
            sql = "select time, operation, speed, targetTemp from log where roomID = '" + ID + "' order by time"
            result = DB_log.query(sql)
            cost = 0
            con = 0
            s = 0
            d = 0
            t = 0
            if result:
                time_last = result[0][0]
                state_last = result[0][1]
                speed_last = result[0][2]
                temp_last = result[0][3]
                for x in result:
                    time = x[0]
                    state = x[1]
                    speed = x[2]
                    temp = x[3]
                    if temp != temp_last:
                        t = t + 1
                    if speed != speed_last:
                        s = s + 1
                    if time == time_last:
                        time_last = time
                        state_last = state
                        speed_last = speed
                        temp_last = temp
                        continue
                    if state_last == 'stop' or state_last == 'pausing' or state_last == 'swap out' or state_last == 'waiting':
                        time_last = time
                        state_last = state
                        speed_last = speed
                        temp_last = temp
                        continue
                    span = self.geTimeSpan(time, time_last)
                    if speed_last == '3':
                        rate = 1
                    elif speed_last == '2':
                        rate = 0.5
                    else:
                        rate = 0.3
                    cost = cost + span * rate
                    con = con + 1
                    d = d + span
                    time_last = time
                    state_last = state
                    speed_last = speed
                    temp_last = temp
                rep.cost = cost
                rep.count = con
                rep.speed = s
                rep.duration = d
                rep.temp = t

            # 获得被调用次数
            sql = "select count(*) from log where roomID = '" + ID + "' and (operation = 'swap in' or operation = 'swap out')"
            result = DB_log.query(sql)
            rep.dispatch = str(result[0][0])
            rep_dict[ID] = rep
        DB_log.DB.close_conn()
        return rep_dict

    def geTimeSpan(self,time_now, time_last):
        data_now = time.strptime(time_now, "%Y-%m-%d %H:%M:%S")  # 定义格式
        data_last = time.strptime(time_last, "%Y-%m-%d %H:%M:%S")  # 定义格式
        time_int_now = int(time.mktime(data_now))
        time_int_last = int(time.mktime(data_last))
        x = (time_int_now - time_int_last)
        span = x // 60
        if x % 60 > 0:
            span = span + 1
        return span

    def get_file_report(self):
        file = open('report.csv','w',encoding='utf-8',newline='')
        csv_w = csv.writer(file)
        csv_w.writerow(['roomID','use_num','duration','fee','dispatch_num','list_num','setTemp_num','setSpeed_num'])
        report_dict = get_replist().get_report()
        for k, v in report_dict.items():
            csv_w.writerow([k,v.open,str(v.duration),str(v.cost),v.dispatch,str(v.count),str(v.temp),str(v.speed)])
        file.close()
        return 'success'




'''list_dict = get_replist().get_alllist()
for x in list_dict.keys():
    print(x)
    for y in list_dict[x]:
        y.print_list()'''