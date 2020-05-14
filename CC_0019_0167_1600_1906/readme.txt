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
