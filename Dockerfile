FROM python:3.8-slim

LABEL maintainer="kirisame@mco.moe"

WORKDIR /code

COPY requirements.txt .

RUN pip install --no-warn-script-location --no-cache-dir --user -r requirements.txt

COPY ./src .

VOLUME [ "/data" ]

CMD [ "python", "-u", "./main.py" ]