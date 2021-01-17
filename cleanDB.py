import mysql.connector
import hvac

try:
	db = mysql.connector.connect(host='172.16.0.2', user='root', passwd='dummypassword', database='alice_data', autocommit=True)
	cursor = db.cursor()

	cursor.execute("DELETE FROM handles")
	cursor.execute("DELETE FROM bb")
	cursor.execute("DELETE FROM currentExchange")
	cursor.execute("DELETE FROM KmeExchangerData")
	#cursor.execute("DELETE FROM completedExchanges")
	cursor.execute("DELETE FROM log")
	cursor.execute("UPDATE exchangedKeys set KEY_COUNT = 0, KEY_IDs = NULL")

	db = mysql.connector.connect(host='172.16.0.2', user='root', passwd='dummypassword', database='bob_data', autocommit=True)
	cursor = db.cursor()

	cursor.execute("DELETE FROM handles")
	cursor.execute("DELETE FROM bb")
	cursor.execute("DELETE FROM currentExchange")
	cursor.execute("DELETE FROM KmeExchangerData")
	#cursor.execute("DELETE FROM completedExchanges")
	cursor.execute("DELETE FROM log")
	cursor.execute("UPDATE exchangedKeys set KEY_COUNT = 0, KEY_IDs = NULL")

	# clean vault
	key = 'an authentication key of 32 byte'
	# alice
	client = hvac.Client(url='http://172.16.0.3:8200')
	client.token = 's.qSYNEKbCQVlGEO9QG4IOmwkd'
	if client.sys.is_sealed():
			client.sys.sumbit_unseal_key('62cbf8b7c181822c774d95d6ae5bd29d8f97f642f30cdcb6cc511869447131dcf8')
			client.sys.sumbit_unseal_key('d818f6a40a94882d78feb4fbf84f89e2b29a5ef6e45d3b3beae4dfc08a06351d63')
	client.secrets.kv.v2.create_or_update_secret(path='storedkeys', secret=dict(keys={'68e3f6d0-d273-11ea-aada-ffeca5cd1502' : key}),)

	# bob
	client = hvac.Client(url='http://172.16.0.4:8200')
	client.token = 's.EOGNOwAgUt6ff6Ifqu3mBp9j'
	if client.sys.is_sealed():
			client.sys.submit_unseal_key('0aa3e6372ca61d6a232f30aadf70e489bbc45787761f89ca8564b2816c98ae9b8d')
			client.sys.submit_unseal_key('f67b2d8eee2f193b046081cb94e45b9b2bbed6996155102dc1ec6676459fa9ffec')

	client.secrets.kv.v2.create_or_update_secret(path='storedkeys', secret=dict(keys={'68e3f6d0-d273-11ea-aada-ffeca5cd1502' : key}),)

	print("DONE")

except Exception as e:
	print("Error occurred:", e)
