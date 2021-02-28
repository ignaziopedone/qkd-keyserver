import requests

x = requests.post('http://localhost:5000/attach_to_server', data=repr('192.168.1.15:4000'))
print(x.status_code)
