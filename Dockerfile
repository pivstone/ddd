FROM daocloud.io/library/python:3.6.2-jessie
COPY sources.list /etc/apt/sources.list
COPY ./requirements requirements

RUN pip3 install -r requirements/base.txt -U -i https://pypi.doubanio.com/simple/

COPY . /srv/ddd/
WORKDIR /srv/ddd/

# CMD python3 manage.py migrate && gunicorn -b 0.0.0.0:80 qing.wsgi
CMD python3 manage.py migrate && python3 manage.py runserver 0.0.0.0:8000