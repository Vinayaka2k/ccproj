# importing required modules
import pika,uuid,json
from flask import Flask, render_template,jsonify,request,abort
import docker,os
from multiprocessing import Value
import math,requests,time,threading
import logging
from kazoo.client import KazooClient
from kazoo.client import KazooState

logging.basicConfig()

# used to count the number of read requests
counter = Value('i', 0)

# indicates the number of slaves that have crashed
slave_crashed = 0

# boolean variable used to check if incoming request is the first request
first_request = True

# connecting to zookeeper client 
zk = KazooClient(hosts='zoo:2181')
zk.start()
zk.delete("/producer", recursive=True)
zk.ensure_path("/producer")

# callback function that is triggered every time a slave gets created/destroyed
# inside this function, we create new slaves for every slave crashed. 
@zk.ChildrenWatch("/producer")
def demo_func(children):
    global slave_crashed
    if(slave_crashed > 0):
        print("slave crashed ......... \n")
        for znode in children:
            data, stat = zk.get("/producer/"+znode)
        createSlave()    
        slave_crashed = slave_crashed - 1
    else:
        for znode in children:
            data, stat = zk.get("/producer/"+znode)

app=Flask(__name__)

client = docker.from_env()

slave_count = 0
client.containers.prune()

# building master and slave images from Dockerfile that exists in current path
client.images.build(path='.',tag='slave') 
client.images.build(path='.',tag='master')

# function to create master container
def createMaster():
    client.containers.run("master",command="python master.py",links={'rmq':'rmq'},network="ccproj_default",detach=True,environment={"worker_type":"master"},auto_remove=True,pid_mode="host",name="master")
    print("------------ MASTER CREATED -------------------")

# function that creates slave containers and increments slave count
def createSlave():
    global slave_count
    slave_count = slave_count+1
    slave_name = "slave" + str(slave_count)
    client.containers.run("slave",command="python master.py",links={'rmq':'rmq'},network="ccproj_default",detach=True,environment={"worker_type":"slave"},auto_remove=True,pid_mode="host",name=slave_name)
    os.system("docker cp master:code/database.db data.db")
    os.system("docker cp data.db "+slave_name+":code/database.db")
    print("------------ SLAVE CREATED -------------------")
    
# function to return list of sorted pids of all worker containers
def worker_list_helper():
    pid_list = []
    for container in client.containers.list():
        if "master" in container.name or "slave" in container.name:
           pid_list.append(container.top()['Processes'][0][2])
    return json.dumps(sorted(pid_list))

# function to crash a slave that has maximum pid
# returns the pid of crashed slave
def crash_slave_helper():
    pid_dict = dict()
    for container in client.containers.list():
        if "slave" in container.name:
           pid_dict[container.top()['Processes'][0][2]] = container
    max_pid = max(pid_dict.keys())
    container = pid_dict[max_pid]
    container.stop()
    client.containers.prune()
    return max_pid

# function to reset the value of counter to zero
def delete_count_requests_helper():
    with counter.get_lock():
        counter.value = 0
    return {}

# function for scaling up/down the number of slaves
# gets expected_no_slaves by performing no_requests/20
# uses worker_list_helper to get current number of slaves
# takes difference between expected and current no_slaves to scale up/down accordingly
def timer():
    global expected_no_slaves
    global counter
    while True:
        no_req = counter.value
        expected_no_slaves = math.ceil(no_req/20)
        if(expected_no_slaves == 0):
            expected_no_slaves = 1
        res = worker_list_helper()
        no_slaves = len(json.loads(res)) - 1
        
        print("no req: ",no_req,"expected no slaves: ",expected_no_slaves,"no slaves: ",no_slaves,"\n\n")
        
        if(no_slaves > expected_no_slaves):
            for i in range(no_slaves-expected_no_slaves):
                crash_slave_helper()
        
        elif(no_slaves < expected_no_slaves):
            for i in range(expected_no_slaves-no_slaves):
                createSlave()

        delete_count_requests_helper()
        time.sleep(120)

# class that defines methods for connecting to rabbitmq service, declaring write queue, publising messages to write queue
# also has a callback function that is triggered on event of getting a response 
class writeMessage(object):
    def __init__(self):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='rmq',heartbeat=600))
        self.channel = self.connection.channel()
        result = self.channel.queue_declare(queue='', exclusive=True)
        self.callback_queue = result.method.queue

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True)

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, json_message):
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key='write_queue',
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=json_message)
        print("sent\n")
        while self.response is None:
           self.connection.process_data_events()
        return int(self.response)

w_msg = writeMessage()

# class that defines methods for connecting to rabbitmq service, declaring read queue, publising messages to read queue
# also has a callback function that is triggered on event of getting a response 
class readMessage(object):
    def __init__(self):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='rmq',heartbeat=600))
        self.channel = self.connection.channel()
        result = self.channel.queue_declare(queue='', exclusive=True)
        self.callback_queue = result.method.queue

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True)

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, json_message):
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key='read_queue',
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=json_message)
        while self.response is None:
           self.connection.process_data_events()
        return json.loads(self.response)

r_msg = readMessage()

# api that gets write requests and publishes them to write queue
@app.route('/api/v1/db/write',methods=["POST"])
def write_database():
    data = request.get_json()
    json_message = json.dumps(data)
    print(" [x] client started ")
    print("JSON: ",json_message)
    response = w_msg.call(json_message)
    print(" [.] Got %r" % response)
    return jsonify(""), response

# api that gets read requests and publishes them to read queue
@app.route('/api/v1/db/read',methods=["POST"])
def read_database():
        print("read request...\n")
        global counter
        with counter.get_lock():
            counter.value += 1
        global first_request
        no_req = counter.value
        if(no_req == 1 and first_request):
                threading.Thread(target=timer).start()
                first_request = False
        data = request.get_json()
        json_message = json.dumps(data)
        result = r_msg.call(json_message)
        return jsonify(result["response"]), result["status"]

# api for crashing master container
@app.route("/api/v1/crash/master",methods=["POST"])
def crash_master():
    for container in client.containers.list():
        if "master" in container.name:
            container.stop()
            client.containers.prune()
    return {},200

# api for returning list of woker pids
@app.route("/api/v1/worker/list",methods=["GET"])
def woker_list():
    return worker_list_helper(),200

# api for crashing slave container
@app.route("/api/v1/crash/slave",methods=["POST"])
def crash_slave():
    global slave_crashed
    slave_crashed = slave_crashed + 1
    return crash_slave_helper(),200

# api for clearing the users and rides table in the database
@app.route('/api/v1/db/clear', methods=["POST"])
def clear_database():
    d = {"data":"clear","table":"clear"}
    e = json.dumps(d)
    response = w_msg.call(e)
    return jsonify(""), 200

# initially, we create one master and one slave containers 
if __name__ == '__main__':
        createMaster()
        createSlave()
        app.debug=True
        app.run('0.0.0.0',use_reloader=False)