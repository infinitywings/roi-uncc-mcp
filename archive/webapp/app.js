const state = {
  datasets: { baseline: null, attack: null },
  activeDatasets: [],
  nodes: { ev: [], power: [] },
  selectedMetric: 'ev',
  selectedNodes: []
};

const metricSelect = document.getElementById('metric-select');
const nodeOptionsEl = document.getElementById('node-options');
const datasetOptionsEl = document.getElementById('dataset-options');
const attackTableBody = document.querySelector('#attack-table tbody');
const switchListEl = document.getElementById('switch-list');
const commandListEl = document.getElementById('command-list');

const NY_LOCALE = { timeZone: 'America/New_York', hour12: false };

function formatDate(date) {
  if (!date) return '';
  return date.toLocaleString('en-US', NY_LOCALE);
}

function handleFileInput(event) {
  const input = event.target;
  const datasetKey = input.dataset.dataset;
  const file = input.files?.[0];
  if (!datasetKey || !file) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const dataset = parseLogFile(e.target.result, datasetKey);
      state.datasets[datasetKey] = dataset;
      if (!state.activeDatasets.includes(datasetKey)) {
        state.activeDatasets.push(datasetKey);
      }
      refreshNodeUniverse();
      renderDatasetOptions();
      renderNodeOptions();
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

function parseLogFile(text, label) {
  const dataset = {
    label,
    observations: [],
    attacks: [],
    decisions: [],
    switches: [],
    recentCommands: [],
    nodes: { ev: [], power: [] }
  };

  const lines = text.split(/\r?\n/).filter(Boolean);
  for (const line of lines) {
    let entry;
    try {
      entry = JSON.parse(line);
    } catch (err) {
      console.warn('Skipping non-JSON line', line);
      continue;
    }

    const event = entry.event;
    if (event === 'grid_observation' && entry.data) {
      const result = entry.data.result || entry.data || {};
      const timestamp = new Date(entry.timestamp);
      const gridState = result.grid_state || {};
      dataset.observations.push({
        timestamp,
        data: gridState,
        systemMetrics: result.system_metrics || {}
      });

      const evNodes = Object.keys(gridState.ev_setpoints_kw || {});
      const powerNodes = Object.keys(gridState.powers || {});
      evNodes.forEach((ev) => {
        if (!dataset.nodes.ev.includes(ev)) dataset.nodes.ev.push(ev);
      });
      powerNodes.forEach((node) => {
        if (!dataset.nodes.power.includes(node)) dataset.nodes.power.push(node);
      });

      if (gridState.blue_team_switches) {
        dataset.switches.push({ timestamp, switches: gridState.blue_team_switches });
      }
      if (gridState.recent_ev_commands) {
        dataset.recentCommands = gridState.recent_ev_commands;
      }
    }

    if (event === 'attack_executed') {
      const action = entry.action || {};
      const result = entry.result || {};
      dataset.attacks.push({
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

    if (event === 'llm_decision') {
      dataset.decisions.push({
        timestamp: new Date(entry.timestamp),
        interactionId: entry.interaction_id,
        actions: entry.actions || [],
        step: entry.step
      });
    }
  }

  dataset.observations.sort((a, b) => a.timestamp - b.timestamp);
  dataset.attacks.sort((a, b) => a.timestamp - b.timestamp);
  dataset.nodes.ev.sort();
  dataset.nodes.power.sort();
  return dataset;
}

function refreshNodeUniverse() {
  const evSet = new Set();
  const powerSet = new Set();
  state.activeDatasets = state.activeDatasets.filter((key) => state.datasets[key]);
  state.activeDatasets.forEach((key) => {
    const ds = state.datasets[key];
    if (!ds) return;
    ds.nodes.ev.forEach((ev) => evSet.add(ev));
    ds.nodes.power.forEach((node) => powerSet.add(node));
  });
  state.nodes.ev = Array.from(evSet).sort();
  state.nodes.power = Array.from(powerSet).sort();
  const available = state.nodes[state.selectedMetric];
  state.selectedNodes = state.selectedNodes.filter((node) => available.includes(node));
  if (!state.selectedNodes.length) {
    state.selectedNodes = available.slice(0, 3);
  }
}

function renderDatasetOptions() {
  datasetOptionsEl.innerHTML = '';
  const entries = Object.entries(state.datasets).filter(([, ds]) => !!ds);
  if (!entries.length) {
    datasetOptionsEl.innerHTML = '<em>No datasets loaded.</em>';
    return;
  }

  entries.forEach(([key, ds]) => {
    const label = document.createElement('label');
    if (state.activeDatasets.includes(key)) label.classList.add('active');

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = state.activeDatasets.includes(key);
    checkbox.addEventListener('change', () => toggleDataset(key));

    const span = document.createElement('span');
    span.textContent = key;

    label.appendChild(checkbox);
    label.appendChild(span);
    datasetOptionsEl.appendChild(label);
  });

  if (!state.activeDatasets.length) {
    const first = entries[0][0];
    state.activeDatasets.push(first);
    refreshNodeUniverse();
    renderDatasetOptions();
  }
}

function renderNodeOptions() {
  nodeOptionsEl.innerHTML = '';
  const nodes = state.selectedMetric === 'ev' ? state.nodes.ev : state.nodes.power;
  if (!nodes.length) {
    nodeOptionsEl.innerHTML = '<em>No nodes in log.</em>';
    return;
  }

  nodes.forEach((node) => {
    const isActive = state.selectedNodes.includes(node);
    const label = document.createElement('label');
    if (isActive) label.classList.add('active');

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
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

function toggleDataset(key) {
  const idx = state.activeDatasets.indexOf(key);
  if (idx >= 0) {
    state.activeDatasets.splice(idx, 1);
  } else {
    state.activeDatasets.push(key);
  }
  if (!state.activeDatasets.length) {
    const first = Object.keys(state.datasets).find((k) => state.datasets[k]);
    if (first) state.activeDatasets.push(first);
  }
  refreshNodeUniverse();
  renderDatasetOptions();
  renderNodeOptions();
  renderChart();
  renderSwitches();
  renderCommands();
  renderAttackTable();
}

function buildSeriesForDataset(dataset, node, metricKey) {
  const xs = [];
  const ys = [];
  dataset.observations.forEach((obs) => {
    const ts = obs.timestamp;
    if (metricKey === 'ev') {
      const value = obs.data.ev_setpoints_kw?.[node];
      if (typeof value === 'number') {
        xs.push(ts);
        ys.push(value);
      }
    } else if (metricKey === 'power') {
      const val = obs.data.powers?.[node];
      if (val && typeof val.real_kw === 'number') {
        xs.push(ts);
        ys.push(val.real_kw);
      }
    }
  });
  return { x: xs, y: ys };
}

function renderChart() {
  const metric = state.selectedMetric;
  const nodes = state.selectedNodes;
  const datasets = state.activeDatasets.map((key) => state.datasets[key]).filter(Boolean);
  if (!datasets.length || !nodes.length) {
    Plotly.newPlot('chart', [], { title: 'No data loaded', paper_bgcolor: 'transparent', plot_bgcolor: 'transparent' });
    return;
  }

  const traces = [];
  datasets.forEach((ds) => {
    nodes.forEach((node) => {
      const series = buildSeriesForDataset(ds, node, metric);
      traces.push({
        x: series.x,
        y: series.y,
        mode: 'lines+markers',
        name: `${node} (${ds.label})`,
        line: { width: 2 }
      });
    });

    if (ds.attacks.length) {
      traces.push({
        x: ds.attacks.map((a) => a.timestamp),
        y: ds.attacks.map((a) => (typeof a.realKw === 'number' ? a.realKw : null)),
        mode: 'markers',
        name: `${ds.label} attacks`,
        marker: { size: 10, color: ds.label === 'attack' ? '#ff6b6b' : '#8884ff', symbol: 'star' },
        text: ds.attacks.map((a) => `${a.evId || 'EV?'} - ${a.realKw ?? '?'} kW`),
        hovertemplate: '%{text}<br>%{x|%Y-%m-%d %H:%M:%S}'
      });
    }
  });

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

function getPrimaryDataset() {
  for (const key of state.activeDatasets) {
    const ds = state.datasets[key];
    if (ds) return ds;
  }
  return Object.values(state.datasets).find(Boolean) || null;
}

function renderAttackTable() {
  attackTableBody.innerHTML = '';
  const rows = [];
  state.activeDatasets.forEach((key) => {
    const ds = state.datasets[key];
    if (!ds) return;
    ds.attacks.forEach((attack) => rows.push({ ...attack, dataset: key }));
  });

  if (!rows.length) {
    attackTableBody.innerHTML = '<tr><td colspan="7">No attacks found in selected datasets.</td></tr>';
    return;
  }

  rows.sort((a, b) => a.timestamp - b.timestamp);
  rows.forEach((attack) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${formatDate(attack.timestamp)}</td>
      <td>${attack.evId ?? ''}</td>
      <td>${attack.realKw ?? ''}</td>
      <td>${attack.sequence ?? ''}</td>
      <td>${attack.step ?? ''}</td>
      <td class="mono">${attack.interactionId ?? ''}</td>
      <td>${attack.status ?? ''} (${attack.dataset})</td>
    `;
    attackTableBody.appendChild(tr);
  });
}

function renderSwitches() {
  switchListEl.innerHTML = '';
  const dataset = getPrimaryDataset();
  if (!dataset || !dataset.switches.length) {
    switchListEl.innerHTML = '<li>No switch telemetry captured.</li>';
    return;
  }
  const latest = dataset.switches[dataset.switches.length - 1];
  Object.entries(latest.switches).forEach(([name, status]) => {
    const li = document.createElement('li');
    li.textContent = `${name}: ${status.is_closed ? 'CLOSED' : 'OPEN'} (${status.status})`;
    switchListEl.appendChild(li);
  });
}

function renderCommands() {
  commandListEl.innerHTML = '';
  const dataset = getPrimaryDataset();
  const commands = dataset?.recentCommands || [];
  if (!commands.length) {
    commandListEl.innerHTML = '<li>No recent commands recorded.</li>';
    return;
  }
  commands.slice(0, 10).forEach((cmd) => {
    const li = document.createElement('li');
    const ts = cmd.timestamp ? new Date(cmd.timestamp) : null;
    li.textContent = `${cmd.ev_id}: ${cmd.real_kw} kW at ${ts ? formatDate(ts) : 'N/A'}`;
    commandListEl.appendChild(li);
  });
}

metricSelect.addEventListener('change', (event) => {
  state.selectedMetric = event.target.value;
  refreshNodeUniverse();
  renderNodeOptions();
  renderChart();
});

Array.from(document.querySelectorAll('.log-input')).forEach((input) => {
  input.addEventListener('change', handleFileInput);
});

renderDatasetOptions();
renderNodeOptions();
renderChart();
renderSwitches();
renderCommands();
renderAttackTable();
*** End of File
