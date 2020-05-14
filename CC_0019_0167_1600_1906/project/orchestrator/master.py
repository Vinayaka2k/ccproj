# importing required modules
from datetime import datetime
from flask import jsonify
import os,time,logging,pika,sqlite3,json

from kazoo.client import KazooClient
from kazoo.client import KazooState
from kazoo.recipe.watchers import DataWatch,ChildrenWatch

logging.basicConfig()

# connecting to the zookeeper service
zk = KazooClient(hosts='zoo:2181')
zk.start()

# ensuring that a path called /producer exists
zk.ensure_path("/producer")

# create a new znode with pid of worker as data inside znode 
zk.create(path="/producer/node",value=str(os.getpid()).encode(),ephemeral=True,sequence=True)

# sleep for 5 seconds to make sure that the database file is copied from master to current slave
time.sleep(5)

# connect to database and get a cursor object
conn = sqlite3.connect('database.db',check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users(\
        username        text primary key,\
        password        text not null\
        );")
conn.commit()

cursor.execute("CREATE TABLE IF NOT EXISTS rides(\
        rideid          integer primary key,\
        username        text,\
        time_stamp      text,\
        source          integer,\
        dest            integer,\
        users           text\
        );")
conn.commit()

print("workers started ")
print(os.environ['worker_type'])
print(os.getpid())

# connecting to the rabbimq service
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='rmq',heartbeat=600))

# creating a channel
channel = connection.channel()

# declaring the required queues
channel.queue_declare(queue='write_queue')
channel.queue_declare(queue='read_queue')
channel.exchange_declare(exchange='sync', exchange_type='fanout')

# function that writes to database based on the input json_msg
# json_msg contains data and table
# indicates table in which data has to be written
def writeDB(json_msg):
	if worker_type == "master":	
		channel.basic_publish(exchange='sync', routing_key='', body=json.dumps(json_msg))
		
	table = json_msg["table"]
	data = json_msg["data"]
	try:
		if(table == "users"):
			cursor.execute("insert into users values (?,?);", (data[0], data[1]))
			conn.commit()
			status=201
		elif(table == "clear"):
			cursor.execute("delete from rides")
    		#conn.commit()
			cursor.execute("delete from users")
			print("deleted")
			status=200
		elif(table == "delete_user"):
			cursor.execute("delete from users where username = ?",(data,))
			status = 200
		elif(table == "delete_ride"):
			cursor.execute("delete from rides where rideid = ?",(data,))
			status = 200
		elif(table == "rides"):
			cursor.execute("insert into rides(rideid, username, time_stamp, source, dest) values (NULL,?,?,?,?);", (data[0], data[1], data[2], data[3]))
			conn.commit()
			status=201
		else:
			cursor.execute("select * from rides where rideid = ?",(data[0],))
			rows = cursor.fetchall()
			row = rows[0]
			if(row[5]):
				users = row[5] + "," + data[1]
			else:
				users = data[1]
			cursor.execute("update rides set users = ? where rideid = ?;", (users,data[0]))
			conn.commit()
			status=200
	except:
		status=400
	print(" status: %r" % status)
	return status

# function that reads from database based on the input json_msg
# json_msg contains data and operation
# indicates operation to be performed on the table
def readDB(json_msg):
	data=json_msg["data"]
	operation=json_msg["operation"]
	if(operation == "check_user_exists"):
		cursor.execute("select * from users where username = ?",(data,))
		rows = cursor.fetchall()
		if(rows):
			status=200
		else:
			status=400
		response = ""
	elif(operation == "list_all_users"):
		cursor.execute("select username from users")
		rows = cursor.fetchall()
		if(rows):
			l = []
			status = 200
			for i in rows:
				l.append(i[0])
			response = l
		else:
			status = 204
			response = ""
	elif(operation == "list_rides"):
		cursor.execute("select * from rides where source = ? and dest = ?",(data[0], data[1]))
		rows = cursor.fetchall()
		response = []
		for row in rows:
			if(True):			
				d = dict()
				d["rideId"] = row[0]
				d["username"] = row[1]
				d["timestamp"] = row[2]
				response.append(d)
		if(response == []):
			status = 204
		else:
			status=200
	elif(operation == "list_ride_details"):
		data = int(data)
		cursor.execute("select * from rides where rideid = ?",(data,))
		rows = cursor.fetchall()
		users_list = []
		if(rows):
			for row in rows:
				username = row[1]
				timestamp = row[2]
				source = row[3]
				dest = row[4]
				users = row[5]
				if(users):
					users_list = users.split(',')
			status=200
			response = {"rideId" : data , "timestamp" : timestamp, "created_by" : username, "source" : source,  "destination" : dest , "users" : users_list}
		else:
			status=204
			response=""
	elif(operation == "check_rideid"):
		data = int(data)
		cursor.execute("select * from rides where rideid = ?",(data,))
		rows = cursor.fetchall()
		if(rows):
			status=200
		else:
			status=400
		response=""
	return {"response":response,"status":status}

# callback function to handle a write request from write queue
# this in turn calls the writeDB method to write data to database
def on_write_request(ch, method, props, body):
    json_msg = json.loads(body)
    response = writeDB(json_msg)
    ch.basic_publish(exchange='',
                     routing_key=props.reply_to,
                     properties=pika.BasicProperties(correlation_id = \
                                                         props.correlation_id),
                     body=str(response))
    ch.basic_ack(delivery_tag=method.delivery_tag)

# callback function to handle a read request from read queue
# this in turn calls the readDB method to read data from database
def on_read_request(ch, method, props, body):
    json_msg = json.loads(body)
    response = readDB(json_msg)
    ch.basic_publish(exchange='',
                     routing_key=props.reply_to,
                     properties=pika.BasicProperties(correlation_id = \
                                                         props.correlation_id),
                     body=json.dumps(response))
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_qos(prefetch_count=1)
worker_type = os.environ['worker_type']

# if worker type is master, consume from write queue
if(worker_type == "master"):
	print("listening to  write queue")
	channel.basic_consume(queue='write_queue', on_message_callback=on_write_request)
	
# else if worker type is slave; consume from read queue as well as sync queue
elif(worker_type == "slave"):
	print("listening to read queue")
	channel.basic_consume(queue='read_queue', on_message_callback=on_read_request)

	result = channel.queue_declare(queue='', exclusive=True)
	queue_name = result.method.queue
	channel.queue_bind(exchange='sync', queue=queue_name)
	print(' listening to sync queue')
	
	# callback method to consume from sync queue and sync data to database  
	def callback(ch, method, properties, body):
		body = json.loads(body)
		writeDB(body)

	channel.basic_consume(
		queue=queue_name, on_message_callback=callback, auto_ack=True)

channel.start_consuming()





























###################################### comment ###################################33
"""
#!/usr/bin/env python
import pika
import time

import sqlite3,json
from datetime import datetime

conn = sqlite3.connect('database.db',check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users(\
	username 	text primary key,\
	password 	text not null\
	);")
conn.commit()

cursor.execute("CREATE TABLE IF NOT EXISTS rides(\
	rideid 		integer primary key,\
	username 	text,\
	time_stamp 	text,\
	source 		integer,\
	dest 		integer,\
	users 		text\
	);")
conn.commit()

###########################################################

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='rmq'))
channel = connection.channel()

channel.queue_declare(queue='task_queue', durable=True)
print(' [*] Waiting for messages.')

def callback(ch, method, properties, body):
	json_msg = json.loads(body)
	table = json_msg["table"]
	#column=request.get_json()["column"]
	data = json_msg["data"]
	#operation=request.get_json()["operation"]
	try:
		if(table == "users"):
			cursor.execute("insert into users values (?,?);", (data[0], data[1]))
			conn.commit()
			status=201
	except:
		status=400
	print(" [x] status: %r" % status)
	#time.sleep(2)
	print(" [x] Done")
	ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue='task_queue', on_message_callback=callback)

channel.start_consuming()

"""
