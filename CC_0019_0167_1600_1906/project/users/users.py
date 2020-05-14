from flask import Flask, render_template,jsonify,request,abort
import sqlite3,requests,json,re,csv,sys
from multiprocessing import Value

from datetime import datetime

counter = Value('i', 0)
base_url = 'http://ec2-3-88-191-217.compute-1.amazonaws.com/api/v1

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
	return "<h2>Welcome to user management !<h2><br /><p>The user microservice is up and running</p>"

# 1. Add user:
@app.route('/api/v1/users',methods=["PUT"])
def add_users():
	with counter.get_lock():
		counter.value += 1

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
	with counter.get_lock():
		counter.value += 1

	data={"data":username, "operation":"check_user_exists"}
	r = requests.post(base_url+'/db/read', json=data)
	if(r.status_code == 400):
		return jsonify(""),400
	
	data = {"data":username,"table":"delete_user"}
	r = requests.post(base_url+'/db/write', json=data)
	return jsonify(""),200

# List all users
@app.route('/api/v1/users', methods=["GET"])
def list_users():
	with counter.get_lock():
		counter.value += 1
	data = {"data":"none", "operation":"list_all_users"}
	r = requests.post(base_url+'/db/read', json=data)
	return r.text, r.status_code

@app.route('/api/v1/_count',methods=["GET"])
def get_count_requests():
	l=[]
	l.append(counter.value)
	return jsonify(l), 200

@app.route('/api/v1/_count',methods=["DELETE"])
def delete_count_requests():
	with counter.get_lock():
		counter.value = 0
	return jsonify(""), 200

# Run the application
if __name__ == '__main__':
	app.debug=True
	app.run('0.0.0.0')
