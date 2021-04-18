import sys
import requests
import json
import base64
import time

thisSAEID = 'SAE11223344'
keyServerIP = '10.0.2.15:4000'


def main():
	try:
		x = requests.post('http://172.16.0.5:8080/auth/realms/quantum_auth/protocol/openid-connect/token', data='client_id=SAE2&client_secret=d2f56afc-3b36-4ed2-a81e-2914f9ce679&grant_type=client_credentials', headers={'Content-Type':'application/x-www-form-urlencoded'})
		token = x.json()['access_token']
	except:
		print("CRITICAL ERROR: access token must be provided in order to talk to key server")
		sys.exit(2)
	oauthHeader = {'Authorization': 'Bearer ' + token}

	# run forever (or until the stop command)
	while(True):
		choice = input("\nPlease insert command:\n 1) Get status\n 2) Get key\n 3) Get key with key ID\n 4) Get preferences\n 5) Set preference\n 6) Get info\n 7) Exit\n[1-7]: ")
		choice = eval(choice)
		if type(choice) is not int or choice < 1 or choice > 7:
			print("Error: please select a valid command by inserting relative number (1-7)")
			continue
		if choice == 1:
			# GET STATUS
			targetSAE = input("Please insert target SAE ID:\n")
			x = requests.get('http://' + keyServerIP + '/api/v1/keys/' + targetSAE + '/status', headers=oauthHeader)
			if x.status_code != 200:
				print("Get status failed with following error code:", x.status_code, x.content)
				continue
			result = x.content
			print("\nGET STATUS result:\n", result)
		elif choice == 2:
			# GET KEY
			targetSAE = input("Please insert target SAE ID:\n")
			number = eval(input("Select number of requested keys:\n"))
			if type(number) is not int:
				print("Error: number must be an integer")
				continue
			klen = eval(input("Select keys length:\n"))
			if type(klen) is not int:
				print("Error: length must be an integer")
				continue
			start = time.time()
			x = requests.post('http://' + keyServerIP + '/api/v1/keys/' + targetSAE + '/enc_keys', data=json.dumps({'number' : number, 'size' : klen, 'SAE_ID' : thisSAEID}), headers=oauthHeader)
			end = time.time()
			if x.status_code != 200:
				print("Get key failed with following error code:", x.status_code, x.content)
				continue
			result = x.content
			print("\nGET KEY result:\n", result)
			print("\nRequest completed in %d seconds" % (end - start))
		elif choice == 3:
			# GET KEY WIHT KEY ID
			targetSAE = input("Please insert target SAE ID:\n")
			knum = eval(input("Please insert the number of key IDs you want to insert:\n"))
			if type(knum) is not int:
				print("Error: number must be an integer")
				continue
			KIDs = []
			for i in range(knum):
				kid = input("Please insert key ID " + str(i) + "\n")
				KIDs.append({'key_ID' : kid})
			x = requests.post('http://' + keyServerIP + '/api/v1/keys/' + targetSAE + '/dec_keys', data=json.dumps({'key_IDs' : KIDs}), headers=oauthHeader)
			if x.status_code != 200:
				print("Get key with key ID failed with following error code:", x.status_code, x.content)
				continue
			result = x.content
			print("\nGET KEY WITH KEY ID result:\n", result)
		elif choice == 4:
			# GET PREFERENCES
			x = requests.get('http://' + keyServerIP + '/api/v1/preferences', headers=oauthHeader)
			if x.status_code != 200:
				print("Get preferences failed with following error code:", x.status_code, x.content)
				continue
			result = x.content
			print("\nGET PREFERENCES result:\n", result)
		elif choice == 5:
			# SET PREFERENCE
			preference = input("Please select preference you want to change\nPossible choices:\n 1) timeout\n 2) log level\n 3) preferred QKD protocol\n[1-3]: ")
			preference = eval(preference)
			if type(preference) is not int or preference < 1 or preference > 3:
				print("Error: please select a valid preference by inserting relative number (1-3)")
				continue
			if preference == 1:
				value = eval(input("Insert new timeout value (in milliseconds)\n"))
				if type(value) is not int:
					print("Error: timeout must be an integer")
					continue
				preference = 'timeout'
			elif preference == 2:
				value = eval(input("Insert desired log level:\n 1) INFO (all events will be logged)\n 2) WARNING (warnings and errors will be logged)\n 3) ERROR (only errors will be logged)\n[1-3] "))
				if type(value) is not int or value < 1 or value > 3:
					print("Error: please select a valid log level by inserting relative number (1-3)")
				if value == 1:
					value = 'INFO'
				elif value == 2:
					value = 'WARNING'
				else:
					value = 'ERROR'
				preference = 'log_level'
			else:
				value = input("Insert preferred QKD protocol:\n")
				preference = 'qkd_protocol'
			x = requests.put('http://' + keyServerIP + '/api/v1/preferences/' + preference, data=json.dumps(str(value)), headers=oauthHeader)
			if x.status_code != 200:
				print("Set preference failed with following error code:", x.status_code, x.content)
				continue
			print("Success")
		elif choice == 6:
			# GET INFO
			info = input("Please select information you want to retrieve\nPossible choices:\n 1) Attached qkd devices\n 2) log\n[1-2]: ")
			info = eval(info)
			if type(info) is not int or info < 1 or info > 2:
				print("Error: please select a valid info by inserting relative number (1-2)")
				continue
			if info == 1:
				x = requests.get('http://' + keyServerIP + '/api/v1/information/qkd_devices', headers=oauthHeader)
			elif info == 2:
				level = eval(input("Insert desired log level:\n 1) INFO\n 2) WARNING\n 3) ERROR\n 4) ALL\n[1-4]: "))
				if type(level) is not int or level < 1 or level > 4:
					print("Error: please select a valid log level by inserting relative number (1-4)")
				if level == 1:
					level = 'INFO'
				elif level == 2:
					level = 'WARNING'
				elif level == 3:
					level = 'ERROR'
				else:
					level = None

				startT = input("Insert start time to retrieve the log from (format 'Year-Month-Day Hour:Minute:Second' - type None if you want to retrieve log from the beginning of time)\n")
				if startT == 'None':
					startT = None
				else:
					try:
						# check that start time is expressed as required
						time.strptime(startT, "%Y-%m-%d %H:%M:%S")
					except ValueError:
						print("Error: start time must be expressed as 'Year-Month-Day Hour:minute:second'. Example '2020-07-20 16:53:15'")
						continue
				if level is not None and startT is not None:
					x = requests.get('http://' + keyServerIP + '/api/v1/information/log?level=' + level +'&startTime=' + startT, headers=oauthHeader)
				elif level is not None:
					x = requests.get('http://' + keyServerIP + '/api/v1/information/log?level=' + level, headers=oauthHeader)
				elif startT is not None:
					x = requests.get('http://' + keyServerIP + '/api/v1/information/log?startTime=' + startT, headers=oauthHeader)
				else:
					x = requests.get('http://' + keyServerIP + '/api/v1/information/log', headers=oauthHeader)
			# check result
			if x.status_code != 200:
				print("Get info failed with following error code:", x.status_code, x.content)
				continue
			result = x.content
			print("\nGET INFO result:\n", result)
		elif choice == 7:
			print("Bye")
			break



if __name__ == "__main__":
	main()
