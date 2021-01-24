import mysql.connector
import hvac
import yaml

pref_file = open("/usr/src/app/config/config.yaml", 'r')
prefs = yaml.safe_load(pref_file)

try:
	db = mysql.connector.connect(host=str(prefs['internal_db']['host']), port=str(prefs['internal_db']['port']), user=str(prefs['internal_db']['user']), passwd=str(prefs['internal_db']['passwd']), database=str(prefs['internal_db']['database']), autocommit=True)
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
	client = hvac.Client(url='http://' + prefs['vault']['host'] + ':' + str(prefs['vault']['port']))
	client.token = prefs['vault']['token']
	if client.sys.is_sealed():
			client.sys.sumbit_unseal_key(prefs['vault']['unseal1'])
			client.sys.submit_unseal_key(prefs['vault']['unseal2'])
	client.secrets.kv.v2.create_or_update_secret(path='storedkeys', secret=dict(keys={'68e3f6d0-d273-11ea-aada-ffeca5cd1502' : key}),)

	print("DONE")

except Exception as e:
	print("Error occurred:", e)
