FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py import_reader.py validation.py ./

COPY templates/ ./templates/
COPY static/ ./static/

EXPOSE 8000

CMD ["python", "-m", "flask", "--app", "main", "run", "--host=0.0.0.0", "--port=8000"]