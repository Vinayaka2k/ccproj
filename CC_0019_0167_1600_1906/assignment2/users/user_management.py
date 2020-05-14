from flask import Flask, render_template,jsonify,request,abort
import sqlite3,requests,json,re,csv

from datetime import datetime

# Connect to database:
conn = sqlite3.connect('user_database.db',check_same_thread=False)
cursor = conn.cursor()

# Create tables if required:
cursor.execute("CREATE TABLE IF NOT EXISTS users(\
	username 	text primary key,\
	password 	text not null\
	);")
conn.commit()

port_num = "8080"
domain = "ec2-3-86-29-107.compute-1.amazonaws.com:"+port_num
base_url = 'http://'+domain+'/api/v1'

def isSHA(str):
	# Ensures that str is in valid SHA format: 40 characters long, case-insensitive and hexadecimal
	if(len(str) != 40):
		return False
	try:
		int(str,16)
	except ValueError:
		return False
	return True

# Start the Flask application:
app=Flask(__name__)

# Functions implementing the APIs
# 0. Test API: To ensure server is up and running
@app.route('/api/v1/userready')
def userready():
	# Server is running
	return "<h2>Welcome to user management !<h2><br /><p>The user microservice is up and running</p>"

# 1. Add user:
@app.route('/api/v1/users',methods=["PUT"])
def add_users():
	username=request.get_json()["username"]
	password=request.get_json()["password"]

	if(isSHA(password) == False):
		return jsonify(""),400

	data = {"data":[username, password],"table":"users"}
	r = requests.post(base_url+'/db/write', json=data)
	return jsonify(""),r.status_code

# 2. Remove user:
@app.route('/api/v1/users/<username>',methods=["DELETE"])
def delete_user(username):	
	data={"data":username, "operation":"check_user_exists"}
	r = requests.post(base_url+'/db/read', json=data)
	if(r.status_code == 400):
		return jsonify(""),400
	cursor.execute("delete from users where username = ?",(username,))
	conn.commit()
	return jsonify(""),200

# assignment 2: List all users
@app.route('/api/v1/users', methods=["GET"])
def list_users():
	data = {"data":"none", "operation":"list_all_users"}
	r = requests.post(base_url+'/db/read', json=data)
	return r.text, r.status_code

# 8. Write to db
@app.route('/api/v1/db/write',methods=["POST"])
def write_database():
	table=request.get_json()["table"]
	#column=request.get_json()["column"]
	data=request.get_json()["data"]
	#operation=request.get_json()["operation"]
	try:
		if(table == "users"):
			cursor.execute("insert into users values (?,?);", (data[0], data[1]))
			conn.commit()
			status=201
	except:
		status=400
	return jsonify(""),status

# 9. Read from db
@app.route('/api/v1/db/read',methods=["POST"])
def read_database():
	#table=request.get_json()["table"]
	#column=request.get_json()["column"]
	data=request.get_json()["data"]
	operation=request.get_json()["operation"]

	if(operation == "check_user_exists"):
		cursor.execute("select * from users where username = ?",(data,))
		rows = cursor.fetchall()
		if(rows):
			status=201
		else:
			status=400
		response = {}
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
			response = {}
	return jsonify(response),status

# Assignment 2: clear db
@app.route('/api/v1/db/clear', methods=["POST"])
def clear_database():
	cursor.execute("delete from users")
	conn.commit()
	return jsonify(""), 200

# Run the application
if __name__ == '__main__':
	app.debug=True
	app.run('0.0.0.0')
