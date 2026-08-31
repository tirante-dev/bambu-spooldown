FROM python:3.13-slim AS build
COPY pyproject.toml README.md /app/
COPY src /app/src
RUN pip install --no-cache-dir --prefix /install /app

FROM python:3.13-slim
COPY --from=build /install /usr/local
RUN useradd --uid 1000 --create-home app && mkdir /data && chown app /data
USER app
ENTRYPOINT ["python", "-m", "spooldown"]
