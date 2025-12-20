# LLM-GridEval attacker server image.
#
# This assumes the HELICS runtime is available in the base image. If you are already
# using `roi-img:latest` for the co-simulation stack, reusing it here keeps HELICS
# and Python wheels consistent.

FROM roi-img:latest

WORKDIR /app/llm_grid_eval

COPY llm_grid_eval/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY llm_grid_eval/src ./src
COPY llm_grid_eval/config ./config

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/llm_grid_eval/src

EXPOSE 5100

CMD ["python", "-m", "llm_grid_eval.server", "--config", "config/default.yaml"]
