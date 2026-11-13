FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
EXPOSE 20
CMD ["uvicorn","app.main:app","--host","109.120.184.20","--port","20"]
