# De Stroomdijk-app. Wordt op de Pi gebouwd (arm64) vanuit ~/stroomdijk/app.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY pyproject.toml ./
COPY stroomdijk ./stroomdijk
RUN pip install --no-cache-dir . && rm -rf /app/build

# zelfde gebruiker als admin op de Pi, zodat bestanden in geheim/ en data/ van admin blijven
USER 1000:1000
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/healthz', timeout=4)"
CMD ["python", "-m", "stroomdijk"]
