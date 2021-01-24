#!/bin/bash

/usr/src/app/config/unseal.sh

python /usr/src/app/src/cleanDB.py

python /usr/src/app/src/KeyServer.py 4000
