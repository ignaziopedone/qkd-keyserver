import requests 
import sys
import logging  


logger = logging.getLogger('QKDMmanager')

def createQksUser(username, password, role ): 
	token = login("admin", "password", "master")
	if token is None: 
		print("ERROR IN LOGIN")
		return None

	auth_header= {'Authorization' : f"Bearer {token}"}
	req_data = {
		"username": username,
		"enabled": True,
		"credentials": [{"value": password, "type": "password",}], 
		"id" : username}

	req_user = requests.post("http://keycloak-service:8080/auth/admin/realms/qks/users", json=req_data, headers=auth_header)
	if req_user.status_code != 201 : 
		print(f"Keycloak unable to create user {username} - {req_user.status_code}")
		return None 

	users = requests.get(f"http://keycloak-service:8080/auth/admin/realms/qks/users?search={username}", headers=auth_header).json() 
	user_id = next((user["id"] for user in users if user["username"] == username), None)
	if user_id is None: 
		return None

	if role == "admin": 
		role_data = [{"id": "29846453-58e3-4b1f-9b85-889429469352", "name" : "admin"}] # admin role id 
	else: 
		role_data = [{"id": "0632e5c5-49b3-4676-b830-a2720a7804a4", "name" : "qkdm"}] # qkdm role id 

	req_role = requests.post(f"http://keycloak-service:8080/auth/admin/realms/qks/users/{user_id}/role-mappings/realm", json=role_data, headers=auth_header)
	if req_role.status_code != 204: 
		print(f"Keycloak unable to add role {role}")
		return None 
	
	print(f"User created: username = {username}, password = {password}, role = {role} ")
	return {"username" : username, "password" : password}

def login(username, password, realm): 
	client_id = "qks"
	client_secret = "4f0d1cd9-4dc8-46b9-9651-fdfe118f53f8"
	try: 
		if realm == "master" : 
			data = f"client_id=admin-cli&grant_type=password&scope=openid&username={username}&password={password}"
			header = {'Content-Type':'application/x-www-form-urlencoded'}  
			x = requests.post(f'http://keycloak-service:8080/auth/realms/{realm}/protocol/openid-connect/token', data=data, headers=header) 
		else: 
			data = f"client_id={client_id}&client_secret={client_secret}&grant_type=password&scope=openid&username={username}&password={password}"
			header = {'Content-Type':'application/x-www-form-urlencoded'}  
			x = requests.post(f'http://keycloak-service:8080/auth/realms/{realm}/protocol/openid-connect/token', data=data, headers=header)
		token = x.json()['access_token']
		return token 
	except Exception as e:
		print(f"login exception: {e}")
		return None  

def registerQKS(QKS_ID, QKS_IP, QKS_port, routing_IP, routing_port): 
	token = login("admin", "password", "qks")
	if token is None: 
		print("ERROR in ADMIN login")
		return False

	qks_reg_data = {
		"QKS_ID" : QKS_ID,
		"QKS_IP" : QKS_IP ,
		"QKS_port" : int(QKS_port) ,
		"routing_IP" : routing_IP ,
		"routing_port" : int(routing_port)
	}
	print("REGISTERING QKS")
	auth_header= {'Authorization' : f"Bearer {token}"}
	x = requests.post(f'http://qks-service:4000/api/v1/qks', json=qks_reg_data, headers=auth_header)
	if x.status_code == 200: 
		print(f"QKS  {QKS_ID} registered ")
		return True
	else: 
		print(f"Error in QKS registration: {x.json()}")
		return False 

def registerQKDM(qkdmID, dest_qks, dest_qkdm) :

	ret = createQksUser(qkdmID, "password", "qkdm")
	if ret is None:
		print("ERROR in user creation") 
		return 

	token = login(ret["username"], ret["password"], "qks")
	if token is None: 
		print("ERROR in QKDM login")
		return 

	auth_header= {'Authorization' : f"Bearer {token}"}
	qkdm_reg_data = {
		'QKDM_ID' : qkdmID, 
		'protocol' : "fake",
		'QKDM_IP' : "qkdm-service",
		'QKDM_port' : "5000", 
		'reachable_QKS' : dest_qks, 
		'reachable_QKDM' : dest_qkdm,
		'max_key_count' : 100, 
		'key_size' : 128 
	}

	
	x = requests.post(f'http://qks-service:4000/api/v1/qkdms', json=qkdm_reg_data, headers=auth_header)
	
	if x.status_code != 200: 
		print(f"ERROR in QKDM registration: {x.json()}") 
	else: 
		res = x.json()
		data = { 'role_id' : res['vault_data']['role_id'], 'secret_id' : res['vault_data']['secret_id'] }
		app_role_login = requests.post(f'http://vault-service:8200/v1/auth/approle/login', json=data)
		res['vault_data']['token'] = app_role_login.json()['auth']['client_token']
		print(res)
	return 

def startQKDMstream(qkdmID): 
	token = login("admin", "password", "qks")
	if token is None: 
		print("ERROR in ADMIN login")
		return False

	auth_header= {'Authorization' : f"Bearer {token}"}
	x = requests.post(f'http://qks-service:4000/api/v1/qkdms/{qkdmID}/streams', headers=auth_header)
	if x.status_code == 200: 
		print(f"KeyStream started on QKDM {qkdmID}")
		return True
	else: 
		print(f"Error in KeyStream creation for QKDM {qkdmID}: {x.json()}")
		return False 

def main(): 
	print(f"EXECUTING WITH: {sys.argv}")
	if int(sys.argv[1]) == 1: 
		ret = createQksUser("admin", "password", "admin")
	if int(sys.argv[1]) == 2: 
		registerQKDM(sys.argv[2], sys.argv[3], sys.argv[4])
	if int(sys.argv[1]) == 3: 
		registerQKS(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
	if int(sys.argv[1]) == 4: 
		startQKDMstream(sys.argv[2])

main()


	


