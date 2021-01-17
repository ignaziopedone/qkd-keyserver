#!/bin/bash

/usr/src/app/config/unseal.sh

python cleanDB.py

python KeyServer.py 4000 &
python qkdmodule/QKDModule.py 5000
