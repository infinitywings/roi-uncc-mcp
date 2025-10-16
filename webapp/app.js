const state = {
  observations: [],
  attacks: [],
  decisions: [],
  switches: [],
  recentCommands: [],
  nodes: { ev: [], power: [] },
  selectedMetric: 'ev',
  selectedNodes: []
};

const metricSelect = document.getElementById('metric-select');
const nodeOptionsEl = document.getElementById('node-options');
const attackTableBody = document.querySelector('#attack-table tbody');
const switchListEl = document.getElementById('switch-list');
const commandListEl = document.getElementById('command-list');

const NY_LOCALE = { timeZone: 'America/New_York', hour12: false };

function formatDate(date) {
  if (!date) return '';
  return date.toLocaleString('en-US', NY_LOCALE);
}

function resetState() {
  state.observations = [];
  state.attacks = [];
  state.decisions = [];
  state.switches = [];
  state.recentCommands = [];
  state.nodes = { ev: [], power: [] };
  state.selectedNodes = [];
}

function handleFileInput(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      parseLogFile(e.target.result);
      populateControls();
      renderChart();
      renderSwitches();
      renderCommands();
      renderAttackTable();
    } catch (err) {
      console.error(err);
      alert('Unable to parse log file. Check the console for details.');
    }
  };
  reader.readAsText(file);
}

function parseLogFile(text) {
  resetState();
  const lines = text.split(/\r?\n/).filter(Boolean);
  for (const line of lines) {
    let entry;
    try {
      entry = JSON.parse(line);
    } catch (err) {
      console.warn('Skipping non-JSON line', line);
      continue;
    }

    if (entry.event === 'grid_observation' && entry.data) {
      const result = entry.data.result || {};
      const timestamp = new Date(entry.timestamp);
      const gridState = result.grid_state || {};
      state.observations.push({
        timestamp,
        data: gridState,
        systemMetrics: result.system_metrics || {}
      });

      const evNodes = Object.keys(gridState.ev_setpoints_kw || {});
      const powerNodes = Object.keys(gridState.powers || {});
      evNodes.forEach((ev) => {
        if (!state.nodes.ev.includes(ev)) state.nodes.ev.push(ev);
      });
      powerNodes.forEach((node) => {
        if (!state.nodes.power.includes(node)) state.nodes.power.push(node);
      });

      if (gridState.blue_team_switches) {
        state.switches.push({ timestamp, switches: gridState.blue_team_switches });
      }
      if (gridState.recent_ev_commands) {
        state.recentCommands = gridState.recent_ev_commands;
      }
    }

    if (entry.event === 'attack_executed') {
      const action = entry.action || {};
      const result = entry.result || {};
      state.attacks.push({
        timestamp: new Date(entry.timestamp),
        evId: action.ev_id,
        realKw: action.real_kw,
        sequence: action.metadata?.sequence,
        step: action.metadata?.step,
        interactionId: action.metadata?.interaction_id,
        status: result.status,
        details: result.result || {}
      });
    }

    if (entry.event === 'llm_decision') {
      state.decisions.push({
        timestamp: new Date(entry.timestamp),
        interactionId: entry.interaction_id,
        actions: entry.actions || [],
        step: entry.step
      });
    }
  }

  state.observations.sort((a, b) => a.timestamp - b.timestamp);
  state.attacks.sort((a, b) => a.timestamp - b.timestamp);
  state.nodes.ev.sort();
  state.nodes.power.sort();
}

function populateControls() {
  if (!state.selectedNodes.length) {
    state.selectedNodes = state.nodes.ev.slice(0, 3);
  }
  renderNodeOptions();
}

function renderNodeOptions() {
  nodeOptionsEl.innerHTML = '';
  const nodes = state.selectedMetric === 'ev' ? state.nodes.ev : state.nodes.power;
  if (!nodes.length) {
    nodeOptionsEl.innerHTML = '<em>No nodes in log.</em>';
    return;
  }

  nodes.forEach((node) => {
    const id = `node-${state.selectedMetric}-${node}`;
    const isActive = state.selectedNodes.includes(node);
    const label = document.createElement('label');
    if (isActive) label.classList.add('active');

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.id = id;
    checkbox.checked = isActive;
    checkbox.addEventListener('change', () => toggleNode(node));

    const span = document.createElement('span');
    span.textContent = node;

    label.appendChild(checkbox);
    label.appendChild(span);
    nodeOptionsEl.appendChild(label);
  });
}

function toggleNode(node) {
  const idx = state.selectedNodes.indexOf(node);
  if (idx >= 0) {
    state.selectedNodes.splice(idx, 1);
  } else {
    state.selectedNodes.push(node);
  }
  renderNodeOptions();
  renderChart();
}

function buildSeries(metricKey) {
  const series = {};
  const nodes = state.selectedNodes;
  for (const node of nodes) {
    series[node] = { x: [], y: [] };
  }

  state.observations.forEach((obs) => {
    const ts = obs.timestamp;
    if (metricKey === 'ev') {
      nodes.forEach((node) => {
        const value = obs.data.ev_setpoints_kw?.[node];
        if (typeof value === 'number') {
          series[node].x.push(ts);
          series[node].y.push(value);
        }
      });
    } else if (metricKey === 'power') {
      nodes.forEach((node) => {
        const val = obs.data.powers?.[node];
        if (val && typeof val.real_kw === 'number') {
          series[node].x.push(ts);
          series[node].y.push(val.real_kw);
        }
      });
    }
  });

  return series;
}

function renderChart() {
  const metric = state.selectedMetric;
  const nodes = state.selectedNodes;
  if (!state.observations.length || !nodes.length) {
    Plotly.newPlot('chart', [], { title: 'No data loaded', paper_bgcolor: 'transparent', plot_bgcolor: 'transparent' });
    return;
  }

  const series = buildSeries(metric);
  const traces = nodes.map((node) => ({
    x: series[node].x,
    y: series[node].y,
    mode: 'lines+markers',
    name: node,
    line: { width: 2 }
  }));

  if (state.attacks.length) {
    traces.push({
      x: state.attacks.map((a) => a.timestamp),
      y: state.attacks.map((a) => (typeof a.realKw === 'number' ? a.realKw : null)),
      mode: 'markers',
      name: 'Attacks',
      marker: { size: 10, color: '#ff6b6b', symbol: 'star' },
      text: state.attacks.map((a) => `${a.evId || 'EV?'} - ${a.realKw ?? '?'} kW`),
      hovertemplate: '%{text}<br>%{x|%Y-%m-%d %H:%M:%S}'
    });
  }

  const layout = {
    title: metric === 'ev' ? 'EV Setpoints' : 'Feeder Power',
    xaxis: { title: 'Time (ET)' },
    yaxis: { title: 'kW' },
    hovermode: 'closest',
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    legend: { orientation: 'h' }
  };

  Plotly.newPlot('chart', traces, layout, { responsive: true });
}

function renderAttackTable() {
  attackTableBody.innerHTML = '';
  if (!state.attacks.length) {
    attackTableBody.innerHTML = '<tr><td colspan="7">No attacks found in log.</td></tr>';
    return;
  }

  state.attacks.forEach((attack) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${formatDate(attack.timestamp)}</td>
      <td>${attack.evId ?? ''}</td>
      <td>${attack.realKw ?? ''}</td>
      <td>${attack.sequence ?? ''}</td>
      <td>${attack.step ?? ''}</td>
      <td class="mono">${attack.interactionId ?? ''}</td>
      <td>${attack.status ?? ''}</td>
    `;
    attackTableBody.appendChild(tr);
  });
}

function renderSwitches() {
  switchListEl.innerHTML = '';
  if (!state.switches.length) {
    switchListEl.innerHTML = '<li>No switch telemetry captured.</li>';
    return;
  }
  const latest = state.switches[state.switches.length - 1];
  Object.entries(latest.switches).forEach(([name, status]) => {
    const li = document.createElement('li');
    li.textContent = `${name}: ${status.is_closed ? 'CLOSED' : 'OPEN'} (${status.status})`;
    switchListEl.appendChild(li);
  });
}

function renderCommands() {
  commandListEl.innerHTML = '';
  if (!state.recentCommands.length) {
    commandListEl.innerHTML = '<li>No recent commands recorded.</li>';
    return;
  }
  state.recentCommands.slice(0, 10).forEach((cmd) => {
    const li = document.createElement('li');
    const ts = cmd.timestamp ? new Date(cmd.timestamp) : null;
    li.textContent = `${cmd.ev_id}: ${cmd.real_kw} kW at ${ts ? formatDate(ts) : 'N/A'}`;
    commandListEl.appendChild(li);
  });
}

metricSelect.addEventListener('change', (event) => {
  state.selectedMetric = event.target.value;
  if (state.selectedMetric === 'ev') {
    state.selectedNodes = state.selectedNodes.filter((node) => state.nodes.ev.includes(node));
    if (!state.selectedNodes.length) state.selectedNodes = state.nodes.ev.slice(0, 3);
  } else {
    state.selectedNodes = state.selectedNodes.filter((node) => state.nodes.power.includes(node));
    if (!state.selectedNodes.length) state.selectedNodes = state.nodes.power.slice(0, 3);
  }
  renderNodeOptions();
  renderChart();
});

document.getElementById('log-file').addEventListener('change', handleFileInput);
