FROM python:3.8-alpine

RUN apk --update add gcc build-base # required to build some of the following pip packages
RUN pip install --no-cache-dir kopf kubernetes requests # install our dependencies
ADD controller.py / 
CMD kopf run /controller.py 