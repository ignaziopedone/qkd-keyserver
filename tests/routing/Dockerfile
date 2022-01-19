FROM python:3.9-alpine

WORKDIR /usr/app

RUN apk --update add gcc build-base
COPY requirements.txt routing/requirements.txt
RUN python -m pip install -r routing/requirements.txt

COPY . routing
WORKDIR /usr/app/routing


EXPOSE 7000 

ENTRYPOINT [ "python", "-u", "asyncRouting_static.py"]
CMD ["config_files/test_conf00.yaml"]
