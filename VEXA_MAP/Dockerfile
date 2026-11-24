FROM python:3.12-slim
WORKDIR /app
COPY server/vexa_map_server.py server/offline_packages.py /app/
EXPOSE 8090
USER 65534:65534
CMD ["python", "-u", "/app/vexa_map_server.py"]
