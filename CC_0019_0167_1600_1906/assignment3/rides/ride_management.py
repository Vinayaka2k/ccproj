from flask import Flask, render_template,jsonify,request,abort
import sqlite3,requests,json,re,csv

from datetime import datetime

# Connect to database:
conn = sqlite3.connect('ride_database.db',check_same_thread=False)
cursor = conn.cursor()

# Create tables if required:
cursor.execute("CREATE TABLE IF NOT EXISTS rides(\
	rideid 		integer primary key,\
	username 	text,\
	time_stamp 	text,\
	source 		integer,\
	dest 		integer,\
	users 		text\
	);")
conn.commit()

# Initialize required parameters:
csv_file = r"AreaNameEnum.csv"
domain = "ec2-3-86-29-107.compute-1.amazonaws.com:8000"
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
	valid_users = requests.get("http://ec2-3-86-29-107.compute-1.amazonaws.com:8080/api/v1/users", json=data)
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
	data={"data":rideId, "operation":"list_ride_details"}
	r = requests.post(base_url+'/db/read', json=data)
	return (r.text, r.status_code,r.headers.items())

# 6. Join an existing ride
@app.route('/api/v1/rides/<rideId>',methods=["POST"])
def join_ride(rideId):
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
	data={"data":rideId, "operation":"check_rideid"}
	r = requests.post(base_url+'/db/read', json=data)
	if(r.status_code == 400):
		return jsonify(""),400
	cursor.execute("delete from rides where rideid = ?",(rideId,))
	conn.commit()
	return jsonify(""),200

# 8. Write to db
@app.route('/api/v1/db/write',methods=["POST"])
def write_database():
	table=request.get_json()["table"]
	#column=request.get_json()["column"]
	data=request.get_json()["data"]
	#operation=request.get_json()["operation"]
	try:
		if(table == "rides"):
			cursor.execute("insert into rides(rideid, username, time_stamp, source, dest) values (NULL,?,?,?,?);", (data[0], data[1], data[2], data[3]))
			conn.commit()
			status=201
		elif(table == "rides_update"):
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
	return jsonify(""),status

# 9. Read from db
@app.route('/api/v1/db/read',methods=["POST"])
def read_database():
	#table=request.get_json()["table"]
	#column=request.get_json()["column"]
	data=request.get_json()["data"]
	operation=request.get_json()["operation"]
	if(operation == "list_rides"):
		cursor.execute("select * from rides where source = ? and dest = ?",(data[0], data[1]))
		rows = cursor.fetchall()
		response = []
		for row in rows:
			if(validDateTime(row[2])):
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
			response={}

	elif(operation == "check_rideid"):
		data = int(data)
		cursor.execute("select * from rides where rideid = ?",(data,))
		rows = cursor.fetchall()
		if(rows):
			status=201
		else:
			status=400
		response={}
	return jsonify(response),status

@app.route('/api/v1/db/clear', methods=["POST"])
def clear_database():
	cursor.execute("delete from rides")
	conn.commit()
	return jsonify(""), 200


# Run the application
if __name__ == '__main__':
	app.debug=True
	app.run('0.0.0.0')
