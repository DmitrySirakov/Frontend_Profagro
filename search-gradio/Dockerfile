FROM python:3.9.16-slim as prod

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY project/ .

CMD python app.py