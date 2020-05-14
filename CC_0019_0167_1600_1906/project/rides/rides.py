from flask import Flask, render_template,jsonify,request,abort
import sqlite3,requests,json,re,csv
from multiprocessing import Value

from datetime import datetime

counter = Value('i', 0)

# Initialize required parameters:
csv_file = r"AreaNameEnum.csv"
domain = "ec2-3-88-191-217.compute-1.amazonaws.com"
base_url = 'http://'+domain+'/api/v1'

# Validation functions used:
def validDateTime(date):
	# Ensures that the date entered is a future date
	datetime_object = datetime.strptime(date, '%d-%m-%Y:%S-%M-%H')
	now = datetime.now()
	return(datetime_object > now)

def validSrcDest(source, destination):
	# Ensures that the source and destination are valid according to the AreaNameEnum.csv

	# Read entire csv into list
	rows = []
	with open(csv_file, 'r') as csvfile:
	    csvreader = csv.reader(csvfile)
	    for row in csvreader:
	        rows.append(row)

	# Check if src and dest are in the file
	src = False
	dest = False
	for i in rows:
	    if(i[0] == str(source)):
	        src = True
	    if(i[0] == str(destination)):
	    	dest = True
	if(src == False or dest == False):
		return False
	return True

def validUsername(username):
	# Checks if given username exists in users database of users microservice
	data={}
	valid_users = requests.get("http://cc-165406227.us-east-1.elb.amazonaws.com/api/v1/users", json=data)
	return username in valid_users.json()

# Start the Flask application:
app=Flask(__name__)

# Functions implementing the APIs
# 0. Test API: To ensure server is up and running
@app.route('/api/v1/rideready')
def rideready():
	# Server is running
	return "<h2>Welcome to ride management !<h2><br /><p>The ride microservice is up and running</p>"

# 3. Create a new ride
@app.route('/api/v1/rides',methods=["POST"])
def create_ride():
	with counter.get_lock():
		counter.value += 1
	
	username=request.get_json()["created_by"]
	source=request.get_json()["source"]
	destination=request.get_json()["destination"]
	timestamp=request.get_json()["timestamp"]
	
	pattern = re.compile("^(3[01]|[12][0-9]|0[1-9])-(1[0-2]|0[1-9])-[0-9]{4}:([0-5]?[0-9])-([0-5]?[0-9])-(2[0-3]|[01][0-9])$")
	if(bool(pattern.match(timestamp)) == False):
		return jsonify(""),400
	
	if(validSrcDest(source, destination) == False):
		return jsonify(""),400
	
	if(validUsername(username) == False):
		return jsonify(""),400
	
	data = {"data":[username, timestamp, source, destination],"table":"rides"}
	r = requests.post(base_url+'/db/write', json=data)
	return jsonify(""),r.status_code

# 4. List all upcoming rides for a given source and destination
@app.route('/api/v1/rides')
def list_rides():
	with counter.get_lock():
		counter.value += 1
	
	source = request.args.get('source')
	dest = request.args.get('destination')
	if(source is None or dest is None):
		return jsonify(""),400

	
	if(validSrcDest(source, dest) == False):
		return jsonify(""),400
		
	data={"data":[source, dest], "operation":"list_rides"}
	r = requests.post(base_url+'/db/read', json=data)
	return (r.text, r.status_code,r.headers.items())

# 5. List all details of a given ride
@app.route('/api/v1/rides/<rideId>')
def list_ride_details(rideId):
	with counter.get_lock():
		counter.value += 1

	data={"data":rideId, "operation":"list_ride_details"}
	r = requests.post(base_url+'/db/read', json=data)
	return (r.text, r.status_code,r.headers.items())

# 6. Join an existing ride
@app.route('/api/v1/rides/<rideId>',methods=["POST"])
def join_ride(rideId):
	with counter.get_lock():
		counter.value += 1

	username=request.get_json()["username"]
	
	if(validUsername(username) == False):
		return jsonify(""),400

	data={"data":rideId, "operation":"check_rideid"}
	r = requests.post(base_url+'/db/read', json=data)

	if(r.status_code == 400):
		return jsonify(""),400
	
	data = {"data":[rideId, username],"table":"rides_update"}
	r = requests.post(base_url+'/db/write', json=data)
	return jsonify(""),r.status_code

# 7. Delete a ride
@app.route('/api/v1/rides/<rideId>',methods=["DELETE"])
def delete_rides(rideId):
	with counter.get_lock():
		counter.value += 1
	
	data={"data":rideId, "operation":"check_rideid"}
	r = requests.post(base_url+'/db/read', json=data)
	if(r.status_code == 400):
		return jsonify(""),400
	
	data = {"data":rideId,"table":"delete_ride"}
	r = requests.post(base_url+'/db/write', json=data)
	return jsonify(""),200

@app.route('/api/v1/rides/count', methods=["GET"])
def get_ride_count():
	with counter.get_lock():
		counter.value += 1

	cursor.execute("select max(rideid) from rides")
	rows = cursor.fetchall()
	if(rows):
		response = rows[0][0]
	else:
		response = 0
	status=200
	l = []
	l.append(response)
	return jsonify(l),status

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
