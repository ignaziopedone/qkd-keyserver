FROM python:3.8-alpine

RUN pip install --no-cache-dir requests 
COPY registerQKDM.py / 
ENTRYPOINT [ "python", "-u", "/registerQKDM.py"]
CMD [ "1" ]