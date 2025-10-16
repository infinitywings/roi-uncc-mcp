# Containerized EV Setpoint MCP server that reuses the simulation base image.
FROM roi-img:latest

WORKDIR /app/ev_setpoint_mcp

# Copy project files into the image
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY config ./config
COPY run_server.py ./
COPY tools ./tools
COPY docker/run_grid_attack_demo.sh ./docker/run_grid_attack_demo.sh
RUN chmod +x ./docker/run_grid_attack_demo.sh

ENV PYTHONUNBUFFERED=1 \
    EV_MCP_SERVER_HOST=0.0.0.0 \
    EV_MCP_SERVER_PORT=5100

EXPOSE 5100

CMD ["/app/ev_setpoint_mcp/docker/run_grid_attack_demo.sh"]
