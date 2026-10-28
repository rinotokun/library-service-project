FROM python:3.12-alpine
LABEL maintainer="rinoto.kun@gmail.com"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt --no-cache-dir

COPY . .

RUN mkdir -p staticfiles/
RUN mkdir -p htmlcov/

RUN adduser \
    --disabled-password \
    --no-create-home \
    my_user

RUN chown -R my_user staticfiles
RUN chmod -R 755 staticfiles

RUN chown -R my_user htmlcov
RUN chmod -R 755 htmlcov

USER my_user
