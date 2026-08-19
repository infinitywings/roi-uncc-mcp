# LLM-GridEval v2 — Container with deps only
# The repo is volume-mounted at /app by docker-compose.

FROM roi-img:latest

COPY llm_grid_eval/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/llm_grid_eval/src

EXPOSE 5100

ENTRYPOINT ["/app/v2/docker/entrypoint.sh"]
