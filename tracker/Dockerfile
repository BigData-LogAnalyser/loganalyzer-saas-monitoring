FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py import_state.py source_reader.py logstash_client.py result_reader.py ./

CMD ["python", "-u", "main.py"]