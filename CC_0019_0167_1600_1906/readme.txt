For assignment 1, both users and rides implementation are done in a single file.

For assignment 2, users and rides are split into seperate microservices and therefore they have seperate databases and they are implemented in seperate python files.

For assignment 3, we add an application load balancer to the existing users and rides microservices and define rules so that the requests are redirected properly.

For the final project, we use orchestator for reading/writing the database and this orchestator will be running in a seperate ec2 instance. 

Folders inside project : 

- Rides folder has following files : 
	1. rides.py : Code that is executed inside rides instance.
	2. Dockerfile
	3. docker-compose

- Users folder has following files : 
	1. users.py : Code that is executed inside users instance.
	2. Dockerfile
	3. docker-compose

- Orchestartor folder has the following files : 
	1. master.py   : Code for worker container - can behave as master or slave.
	2. producer.py : Code for orchestrator. Its a flask application.

Execution : 

To run these files, just go to all 3 directories - users, rides and orchestartor and execute sudo docker-compose up so that all 3 containers are created. Then we can call the apis accordingly. 


PROJECT DETAILS: 

users.py is the flask application that is run inside a container with a python env and contains code to perform CRUD operations on Users. Similarly, rides.py is the flask application that is run inside another container and contains code for performing CRUD on Rides. The DB read/write are abstracted from the users program and are performed by the DBaaS service, which exposes a URL that is used by the users and rides services to access the DB. 

The entire DBaaS service, consisting of orchestator and worker containers makes use of RabbitMQ as a message broker and kazoo module of python as the zookeeper, in order to watch the child nodes.

producer.py is a flask application for the orchestrator and it is used to ensure scalability and fault tolerance. Scalability is ensured by spinning up new worker containers when the number of requests are high and spinning down a few containers when the system has a low load. High availibility and fault-tolerance is ensured by the use of kazoo module in python, which functions as a zookeeper and a method called childWatch is implemented in the orchestartor that keeps track of all the child znodes inside the /producer path. Also, the images for the worker containers are built and initially, one master and one slave continer is spun up using this image, by utilizing docker sdk.

master.py is a flask app for the worker nodes - master and slaves. Master container declares and susbscribes to the write queue, using which it consumes the write requests published by the orchestator. In order to handle a write request, a class called writeRequest is created, that has if clauses which select the DB write commnd to be executed based on the operation requested by the user. 
Similarly, slave container declares and subscribes to the read queue, using which it consumes the read requests published by the orchestator. For handling a read request, a class named readRequest is created, that selects the exact DB read to be performed based on the opertaion requested by the user. 

A "sync" queue is established between the master and the slave, so that the slave container is able to sync all the DB writes performed dby the master. This is required since both master and slave have their own instances of the DB, and if a master receives a write requests and performs an update to it;s DB, it's not reflected in the slaves DB. Fanout exchange in RabbitMq is used to handle the sync requests and the .db file of slave is replaced by the .db file of master in order for the slave to update it's DB.







