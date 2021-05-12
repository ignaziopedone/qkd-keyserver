from flask import request, Flask
import requests 
import vaultClient 
import uuid 
import json
import sys

app = Flask(__name__)
serverPort = 8080 

@app.route("/", methods=['GET'])
def welcome() : 
    return json.dumps("Key Server is running"), 200

@app.route("/api/v1/keys/<slave_SAE_ID>/status", methods=['GET'])
def getStatus(slave_SAE_ID):
    # TODO: api function
    return json.dumps(f"get getStatus for {slave_SAE_ID}"), 200

@app.route("/api/v1/keys/<slave_SAE_ID>/enc_keys", methods=['POST'])
def getKey(slave_SAE_ID):
    # TODO: check for JSON fields
    # TODO: api function
    content = request.get_json()
    return json.dumps(content), 200

@app.route("/api/v1/keys/<master_SAE_ID>/dec_keys", methods=['POST'])
def getKeyWithKeyIDs(master_SAE_ID):
    # TODO: check for JSON fields
    # TODO: api function
    content = request.get_json()
    return json.dumps(content), 200



def main() : 
    global app, serverPort

    if (len(sys.argv) > 1) : 
        try: 
            serverPort = int(sys.argv[1])
            if (serverPort < 0 or serverPort > 2**16 - 1):
                raise Exception
        except: 
            print("ERROR: use 'python3 appname <port>', port must be integer")

    # check vault init
    # check db init 

    app.run(host='0.0.0.0', port=serverPort)


if __name__ == "__main__":
	main()
