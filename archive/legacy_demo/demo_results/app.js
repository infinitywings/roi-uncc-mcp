// ROI UNCC MCP Attack Visualization App
class AttackVisualizer {
    constructor() {
        this.currentData = null;
        this.charts = {};
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadSampleData();
    }

    setupEventListeners() {
        // File upload
        document.getElementById('fileInput').addEventListener('change', (e) => {
            this.loadFile(e.target.files[0]);
        });

        // Load sample button
        document.getElementById('loadSample').addEventListener('click', () => {
            this.loadSampleData();
        });

        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });
    }

    loadFile(file) {
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const data = JSON.parse(e.target.result);
                this.loadData(data);
            } catch (error) {
                alert('Error parsing JSON: ' + error.message);
            }
        };
        reader.readAsText(file);
    }

    loadSampleData() {
        // Load the working AI example file
        fetch('./working_ai_example.json')
            .then(response => response.json())
            .then(data => this.loadData(data))
            .catch(() => {
                // Fallback sample data
                const sampleData = {
                    ai_results: [{
                        attack_count: 0,
                        effectiveness_score: 0.0,
                        attacks: []
                    }],
                    random_results: [{
                        attack_count: 11,
                        effectiveness_score: 0.0,
                        attacks: [
                            {
                                technique: "block_command",
                                impact: { total_impact_score: 0.029813 },
                                timestamp: "2025-06-30T19:36:22.622627"
                            },
                            {
                                technique: "spoof_data",
                                impact: { total_impact_score: 0.0 },
                                timestamp: "2025-06-30T19:36:51.204829"
                            }
                        ]
                    }],
                    comparison_metrics: {
                        ai_mean: 0.0,
                        random_mean: 0.0,
                        improvement_ratio: "Infinity",
                        ai_success_rate: 0.0,
                        random_success_rate: 0.0
                    }
                };
                this.loadData(sampleData);
            });
    }

    loadData(data) {
        // Normalize data format to handle both comparison and individual campaign formats
        this.currentData = this.normalizeData(data);
        this.showDataStatus(data);
        this.updateOverview();
        this.updateTimelines();
        this.updateComparison();
    }

    showDataStatus(originalData) {
        // Show what type of data was loaded
        let statusText = '';
        let statusClass = '';
        
        if (originalData.ai_results || originalData.random_results || originalData.comparison_metrics) {
            statusText = '📊 Comparison study data loaded';
            statusClass = 'status-comparison';
        } else if (originalData.type === 'ai_strategic_campaign' || originalData.ai_decisions) {
            statusText = `🤖 AI campaign loaded (${originalData.attack_count || 0} attacks)`;
            statusClass = 'status-ai';
        } else if (originalData.type === 'random_campaign') {
            statusText = `🎲 Random campaign loaded (${originalData.attack_count || 0} attacks)`;
            statusClass = 'status-random';
        } else {
            statusText = `📄 Data loaded (${originalData.attacks?.length || 0} attacks)`;
            statusClass = 'status-unknown';
        }
        
        // Update or create status indicator
        let statusDiv = document.getElementById('data-status');
        if (!statusDiv) {
            statusDiv = document.createElement('div');
            statusDiv.id = 'data-status';
            statusDiv.style.cssText = `
                position: fixed;
                top: 10px;
                right: 10px;
                padding: 10px 15px;
                background: rgba(0, 0, 0, 0.8);
                color: white;
                border-radius: 5px;
                font-size: 14px;
                z-index: 1000;
                border-left: 4px solid #ff6b35;
            `;
            document.body.appendChild(statusDiv);
        }
        
        statusDiv.textContent = statusText;
        statusDiv.className = statusClass;
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            if (statusDiv) statusDiv.style.opacity = '0.3';
        }, 5000);
    }

    normalizeData(data) {
        console.log('Normalizing data:', data);
        
        // If data is already in comparison format, return as-is
        if (data.ai_results || data.random_results || data.comparison_metrics) {
            console.log('Data already in comparison format');
            return data;
        }

        // Detect individual campaign format and convert to comparison format
        const normalizedData = {
            ai_results: [],
            random_results: [],
            comparison_metrics: {
                ai_mean: 0,
                random_mean: 0,
                improvement_ratio: 0,
                ai_success_rate: 0,
                random_success_rate: 0
            }
        };

        // Check if this is an AI campaign
        if (data.type === 'ai_strategic_campaign' || data.ai_decisions || data.ai_decision_count) {
            console.log('Detected AI campaign, converting...');
            normalizedData.ai_results = [{
                attack_count: data.attack_count || 0,
                effectiveness_score: data.effectiveness_score || 0,
                attacks: data.attacks || [],
                duration: data.duration,
                start_time: data.start_time,
                end_time: data.end_time,
                type: data.type
            }];
            normalizedData.comparison_metrics.ai_mean = data.effectiveness_score || 0;
            normalizedData.comparison_metrics.ai_success_rate = this.calculateSuccessRate(data.attacks || []);
            console.log('AI results created:', normalizedData.ai_results[0]);
        }
        // Check if this is a random campaign
        else if (data.type === 'random_campaign' || (!data.ai_decisions && data.attacks)) {
            normalizedData.random_results = [{
                attack_count: data.attack_count || 0,
                effectiveness_score: data.effectiveness_score || 0,
                attacks: data.attacks || [],
                duration: data.duration,
                start_time: data.start_time,
                end_time: data.end_time,
                type: data.type
            }];
            normalizedData.comparison_metrics.random_mean = data.effectiveness_score || 0;
            normalizedData.comparison_metrics.random_success_rate = this.calculateSuccessRate(data.attacks || []);
        }

        // Calculate improvement ratio
        const aiMean = normalizedData.comparison_metrics.ai_mean;
        const randomMean = normalizedData.comparison_metrics.random_mean;
        if (randomMean === 0 && aiMean > 0) {
            normalizedData.comparison_metrics.improvement_ratio = "Infinity";
        } else if (randomMean > 0) {
            normalizedData.comparison_metrics.improvement_ratio = aiMean / randomMean;
        }

        return normalizedData;
    }

    calculateSuccessRate(attacks) {
        if (!attacks || attacks.length === 0) return 0;
        const successfulAttacks = attacks.filter(attack => 
            attack.success === true || 
            (attack.impact && attack.impact.total_impact_score > 0)
        ).length;
        return successfulAttacks / attacks.length;
    }

    switchTab(tabName) {
        console.log('🔄 Switching to tab:', tabName);
        
        // Hide all tabs
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.querySelectorAll('.tab').forEach(tab => {
            tab.classList.remove('active');
        });

        // Show selected tab
        const tabContent = document.getElementById(tabName);
        const tabButton = document.querySelector(`[data-tab="${tabName}"]`);
        
        if (tabContent) {
            tabContent.classList.add('active');
            console.log('✅ Tab content activated:', tabName);
        } else {
            console.error('❌ Tab content not found:', tabName);
        }
        
        if (tabButton) {
            tabButton.classList.add('active');
            console.log('✅ Tab button activated:', tabName);
        } else {
            console.error('❌ Tab button not found:', tabName);
        }
        
        // If switching to timeline tab and we have data, ensure chart is created
        if (tabName === 'timeline' && this.currentData) {
            console.log('📊 Creating timeline chart for timeline tab');
            setTimeout(() => this.createTimelineChart(), 100);
        }
    }

    updateOverview() {
        if (!this.currentData) return;

        const metrics = this.currentData.comparison_metrics || {};

        // Update metric cards
        document.getElementById('ai-effectiveness').textContent = (metrics.ai_mean || 0).toFixed(6);
        document.getElementById('random-effectiveness').textContent = (metrics.random_mean || 0).toFixed(6);
        
        const ratio = metrics.improvement_ratio;
        document.getElementById('improvement-ratio').textContent = 
            (ratio === "Infinity" || ratio === Infinity) ? '∞' : (parseFloat(ratio) || 0).toFixed(2) + 'x';

        const totalAttacks = (this.currentData.ai_results?.[0]?.attack_count || 0) + 
                           (this.currentData.random_results?.[0]?.attack_count || 0);
        document.getElementById('total-attacks').textContent = totalAttacks;

        // Create overview chart
        this.createOverviewChart();
    }

    updateTimelines() {
        if (!this.currentData) return;

        // AI Timeline (both main timeline tab and detailed AI tab)
        const aiTimeline = document.getElementById('ai-timeline');
        const aiTimelineDetailed = document.getElementById('ai-timeline-detailed');
        const aiData = this.currentData.ai_results?.[0];
        
        const aiContent = aiData?.attacks?.length > 0 
            ? aiData.attacks.map((attack, i) => this.createAttackItem(attack, i + 1)).join('')
            : '<div class="no-data">No AI attacks executed</div>';
        
        if (aiTimeline) aiTimeline.innerHTML = aiContent;
        if (aiTimelineDetailed) aiTimelineDetailed.innerHTML = aiContent;

        // Random Timeline
        const randomTimeline = document.getElementById('random-timeline');
        const randomData = this.currentData.random_results?.[0];
        
        const randomContent = randomData?.attacks?.length > 0 
            ? randomData.attacks.map((attack, i) => this.createAttackItem(attack, i + 1)).join('')
            : '<div class="no-data">No random attacks executed</div>';
            
        if (randomTimeline) randomTimeline.innerHTML = randomContent;

        // Update random attacks detailed tab
        const randomTimelineDetailed = document.getElementById('random-timeline-detailed');
        if (randomTimelineDetailed) randomTimelineDetailed.innerHTML = randomContent;

        // Create interactive timeline charts
        this.createTimelineChart();
    }

    updateComparison() {
        if (!this.currentData) return;

        const metrics = this.currentData.comparison_metrics || {};
        const aiData = this.currentData.ai_results?.[0] || {};
        const randomData = this.currentData.random_results?.[0] || {};

        // Update comparison stats
        document.getElementById('ai-success').textContent = 
            ((metrics.ai_success_rate || 0) * 100).toFixed(1) + '%';
        document.getElementById('random-success').textContent = 
            ((metrics.random_success_rate || 0) * 100).toFixed(1) + '%';
        document.getElementById('ai-count').textContent = aiData.attack_count || 0;
        document.getElementById('random-count').textContent = randomData.attack_count || 0;

        // Update progress bars
        const maxEffectiveness = Math.max(metrics.ai_mean || 0, metrics.random_mean || 0, 0.1);
        document.getElementById('ai-progress').style.width = 
            ((metrics.ai_mean || 0) / maxEffectiveness * 100) + '%';
        document.getElementById('random-progress').style.width = 
            ((metrics.random_mean || 0) / maxEffectiveness * 100) + '%';

        // Create comparison chart
        this.createComparisonChart();
    }

    createAttackItem(attack, index) {
        const impact = attack.impact?.total_impact_score || 0;
        const timestamp = new Date(attack.timestamp).toLocaleTimeString();
        
        let details = `Impact: ${impact.toFixed(6)}`;
        
        // Add technique-specific details
        const technique = attack.technique || attack.attack_type;
        
        if (technique === 'spoof_data' || technique === 'voltage_spoof') {
            if (attack.magnitude || attack.injected_voltage) {
                const voltage = attack.magnitude || attack.injected_voltage?.real || 0;
                details += ` | Voltage: ${voltage.toFixed(1)}V`;
            }
            if (attack.target_phase) {
                details += ` | Phase: ${attack.target_phase}`;
            }
        } else if (technique === 'inject_load' || technique === 'load_injection') {
            if (attack.magnitude_va || attack.injected_load) {
                const power = attack.magnitude_va || 
                             (attack.injected_load?.real ? Math.sqrt(Math.pow(attack.injected_load.real, 2) + Math.pow(attack.injected_load.imag, 2)) : 0);
                details += ` | Power: ${(power/1000000).toFixed(1)}MVA`;
            }
            if (attack.power_factor) {
                details += ` | PF: ${attack.power_factor}`;
            }
        } else if (technique === 'reconnaissance') {
            if (attack.attack_surfaces && attack.attack_surfaces.length > 0) {
                details += ` | Found: ${attack.attack_surfaces.length} attack surfaces`;
            } else if (attack.grid_topology) {
                details += ` | Topology mapped`;
            } else {
                details += ` | System reconnaissance`;
            }
        } else if (technique === 'block_command' || technique === 'command_blocking') {
            if (attack.duration) {
                details += ` | Duration: ${attack.duration}s`;
            }
            if (attack.blocking_enabled !== undefined) {
                details += ` | Enabled: ${attack.blocking_enabled}`;
            } else {
                details += ` | Commands blocked`;
            }
        }
        
        // Add success indicator
        const successIcon = attack.success === true ? '✅' : 
                           attack.success === false ? '❌' : 
                           impact > 0 ? '✅' : '⚠️';
        
        return `
            <div class="attack-item">
                <div class="attack-type">${successIcon} ${index}. ${technique}</div>
                <div class="attack-details">${details}</div>
                <div class="attack-timestamp">${timestamp}</div>
            </div>
        `;
    }

    createOverviewChart() {
        if (typeof Chart === 'undefined') {
            console.warn('Chart.js not available');
            return;
        }

        const ctx = document.getElementById('overviewChart').getContext('2d');
        
        if (this.charts.overview) this.charts.overview.destroy();
        
        const metrics = this.currentData?.comparison_metrics || {};
        
        this.charts.overview = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['AI Strategy', 'Random Strategy'],
                datasets: [{
                    label: 'Effectiveness Score',
                    data: [metrics.ai_mean || 0, metrics.random_mean || 0],
                    backgroundColor: ['rgba(255, 107, 53, 0.8)', 'rgba(128, 128, 128, 0.8)'],
                    borderColor: ['rgba(255, 107, 53, 1)', 'rgba(128, 128, 128, 1)'],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: { 
                        beginAtZero: true,
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        ticks: { color: 'white' }
                    },
                    x: { 
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        ticks: { color: 'white' }
                    }
                }
            }
        });
    }

    createComparisonChart() {
        if (typeof Chart === 'undefined') {
            console.warn('Chart.js not available');
            return;
        }

        const ctx = document.getElementById('comparisonChart').getContext('2d');
        
        if (this.charts.comparison) this.charts.comparison.destroy();
        
        const metrics = this.currentData?.comparison_metrics || {};
        
        this.charts.comparison = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['Success Rate (%)', 'Effectiveness', 'Attack Count'],
                datasets: [
                    {
                        label: 'AI Strategy',
                        data: [
                            (metrics.ai_success_rate || 0) * 100,
                            (metrics.ai_mean || 0) * 100,
                            (this.currentData.ai_results?.[0]?.attack_count || 0)
                        ],
                        borderColor: 'rgba(255, 107, 53, 1)',
                        backgroundColor: 'rgba(255, 107, 53, 0.2)',
                        pointBackgroundColor: 'rgba(255, 107, 53, 1)'
                    },
                    {
                        label: 'Random Strategy',
                        data: [
                            (metrics.random_success_rate || 0) * 100,
                            (metrics.random_mean || 0) * 100,
                            (this.currentData.random_results?.[0]?.attack_count || 0)
                        ],
                        borderColor: 'rgba(128, 128, 128, 1)',
                        backgroundColor: 'rgba(128, 128, 128, 0.2)',
                        pointBackgroundColor: 'rgba(128, 128, 128, 1)'
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { 
                        labels: { color: 'white' }
                    }
                },
                scales: {
                    r: {
                        angleLines: { color: 'rgba(255, 255, 255, 0.3)' },
                        grid: { color: 'rgba(255, 255, 255, 0.3)' },
                        pointLabels: { color: 'white' },
                        ticks: { 
                            color: 'white',
                            backdropColor: 'transparent'
                        }
                    }
                }
            }
        });
    }

    createTimelineChart() {
        if (typeof Chart === 'undefined') {
            console.warn('Chart.js not available');
            return;
        }

        const timelineCanvas = document.getElementById('timelineChart');
        if (!timelineCanvas) {
            console.warn('Timeline canvas not found');
            return;
        }

        const ctx = timelineCanvas.getContext('2d');
        
        if (this.charts.timeline) this.charts.timeline.destroy();

        // Prepare timeline data
        const timelineData = this.prepareTimelineData();
        
        console.log('Creating timeline chart with data:', timelineData);
        
        if (!timelineData.datasets || timelineData.datasets.length === 0) {
            console.warn('No timeline data available');
            // Clear the canvas and show a message
            ctx.clearRect(0, 0, timelineCanvas.width, timelineCanvas.height);
            ctx.font = '16px Arial';
            ctx.fillStyle = 'white';
            ctx.textAlign = 'center';
            ctx.fillText('No attack data available for timeline visualization', 
                        timelineCanvas.width / 2, timelineCanvas.height / 2);
            return;
        }
        
        this.charts.timeline = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: timelineData.datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Attack Timeline and System Impact',
                        color: 'white',
                        font: { size: 16 }
                    },
                    legend: { 
                        labels: { color: 'white' }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: 'white',
                        bodyColor: 'white',
                        borderColor: 'rgba(255, 107, 53, 0.8)',
                        borderWidth: 1,
                        callbacks: {
                            title: function(context) {
                                const point = context[0];
                                if (point.dataset.label === 'Attack Events') {
                                    const attack = timelineData.attacks[point.dataIndex];
                                    return `${attack.technique} Attack`;
                                }
                                return `Time: ${point.label}s`;
                            },
                            label: function(context) {
                                const point = context;
                                if (point.dataset.label === 'Attack Events') {
                                    const attack = timelineData.attacks[point.dataIndex];
                                    return [
                                        `Type: ${attack.technique}`,
                                        `Impact: ${attack.impact.total_impact_score.toFixed(6)}`,
                                        `Success: ${attack.success ? 'Yes' : 'No'}`,
                                        `Time: ${new Date(attack.timestamp).toLocaleTimeString()}`
                                    ];
                                }
                                return `${point.dataset.label}: ${point.parsed.y.toFixed(6)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        position: 'bottom',
                        title: {
                            display: true,
                            text: 'Time (seconds from start)',
                            color: 'white'
                        },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        ticks: { color: 'white' }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'System Impact / Voltage (pu)',
                            color: 'white'
                        },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        ticks: { color: 'white' }
                    }
                }
            }
        });
    }


    prepareTimelineData() {
        const aiData = this.currentData.ai_results?.[0];
        const randomData = this.currentData.random_results?.[0];
        
        console.log('Preparing timeline data - AI:', aiData, 'Random:', randomData);
        
        const datasets = [];
        const attacks = [];
        
        // Helper function to convert timestamp to seconds from start
        const getTimeOffset = (timestamp, startTime) => {
            const attackTime = new Date(timestamp);
            const start = new Date(startTime);
            return (attackTime - start) / 1000; // Convert to seconds
        };

        // Process AI attacks
        if (aiData?.attacks?.length > 0) {
            const startTime = aiData.start_time;
            console.log('AI start time:', startTime);
            console.log('AI attacks:', aiData.attacks);
            
            const aiAttackPoints = [];
            const voltagePoints = [];
            const impactPoints = [];
            
            aiData.attacks.forEach((attack, index) => {
                console.log(`Processing attack ${index}:`, attack);
                
                const timeOffset = getTimeOffset(attack.timestamp, startTime);
                const impact = attack.impact?.total_impact_score || 0;
                
                console.log(`Attack ${index} - Time offset: ${timeOffset}s, Impact: ${impact}`);
                
                // Attack event markers
                aiAttackPoints.push({
                    x: timeOffset,
                    y: Math.max(impact * 1000000, 0.1), // Scale up for visibility
                    attack: attack
                });
                
                // Voltage impact line
                if (attack.technique === 'spoof_data' && attack.magnitude) {
                    const voltagePU = attack.magnitude / 2401.78; // Convert to per unit
                    voltagePoints.push({
                        x: timeOffset,
                        y: voltagePU
                    });
                    console.log(`Added voltage point: ${timeOffset}s, ${voltagePU} pu`);
                }
                
                // Cumulative impact
                impactPoints.push({
                    x: timeOffset,
                    y: impact
                });
                
                attacks.push(attack);
            });
            
            console.log('AI attack points:', aiAttackPoints);
            console.log('Voltage points:', voltagePoints);
            console.log('Impact points:', impactPoints);

            // Attack events as scatter plot
            datasets.push({
                label: 'Attack Events',
                type: 'scatter',
                data: aiAttackPoints,
                backgroundColor: 'rgba(255, 107, 53, 0.8)',
                borderColor: 'rgba(255, 107, 53, 1)',
                pointRadius: 10,
                pointHoverRadius: 15,
                pointStyle: 'triangle',
                showLine: false
            });

            // System impact line
            if (impactPoints.length > 0) {
                // Add baseline points
                impactPoints.unshift({ x: 0, y: 0 });
                impactPoints.push({ x: (aiData.duration || 60), y: impactPoints[impactPoints.length - 1].y });
                
                datasets.push({
                    label: 'System Impact',
                    type: 'line',
                    data: impactPoints,
                    borderColor: 'rgba(255, 107, 53, 0.6)',
                    backgroundColor: 'rgba(255, 107, 53, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3,
                    pointHoverRadius: 6
                });
            }

            // Voltage line (if available)
            if (voltagePoints.length > 0) {
                voltagePoints.unshift({ x: 0, y: 1.0 }); // Nominal voltage
                
                datasets.push({
                    label: 'Voltage (pu)',
                    type: 'line',
                    data: voltagePoints,
                    borderColor: 'rgba(255, 193, 7, 0.8)',
                    backgroundColor: 'rgba(255, 193, 7, 0.1)',
                    fill: false,
                    tension: 0.2,
                    pointRadius: 4,
                    pointHoverRadius: 7
                });
            }
        }

        // Process Random attacks (if available)
        if (randomData?.attacks?.length > 0) {
            const startTime = randomData.start_time;
            const randomAttackPoints = [];
            
            randomData.attacks.forEach((attack) => {
                const timeOffset = getTimeOffset(attack.timestamp, startTime);
                const impact = attack.impact?.total_impact_score || 0;
                
                randomAttackPoints.push({
                    x: timeOffset,
                    y: Math.max(impact * 1000000, 0.05), // Scale up for visibility
                    attack: attack
                });
                
                attacks.push(attack);
            });

            datasets.push({
                label: 'Random Attack Events',
                type: 'scatter',
                data: randomAttackPoints,
                backgroundColor: 'rgba(128, 128, 128, 0.6)',
                borderColor: 'rgba(128, 128, 128, 1)',
                pointRadius: 6,
                pointHoverRadius: 10,
                pointStyle: 'circle',
                showLine: false
            });
        }

        return { datasets, attacks };
    }

    // Load and parse simulation data from CSV files
    async loadSimulationData() {
        const simulationData = {
            gridlabd: null,
            gridpack: null,
            regulator: null
        };

        try {
            // Load GridLAB-D data
            const gldResponse = await fetch('./gld_cosim_right.csv');
            if (gldResponse.ok) {
                const gldText = await gldResponse.text();
                simulationData.gridlabd = this.parseGridLabDData(gldText);
                console.log('✅ GridLAB-D simulation data loaded:', simulationData.gridlabd.length, 'points');
            }
        } catch (e) {
            console.warn('GridLAB-D data not available:', e.message);
        }

        try {
            // Load GridPACK data
            const gpkResponse = await fetch('./gpk.csv');
            if (gpkResponse.ok) {
                const gpkText = await gpkResponse.text();
                simulationData.gridpack = this.parseGridPackData(gpkText);
                console.log('✅ GridPACK simulation data loaded:', simulationData.gridpack.length, 'points');
            }
        } catch (e) {
            console.warn('GridPACK data not available:', e.message);
        }

        try {
            // Load Regulator data
            const regResponse = await fetch('./reg1_output.csv');
            if (regResponse.ok) {
                const regText = await regResponse.text();
                simulationData.regulator = this.parseRegulatorData(regText);
                console.log('✅ Regulator simulation data loaded:', simulationData.regulator.length, 'points');
            }
        } catch (e) {
            console.warn('Regulator data not available:', e.message);
        }

        return simulationData;
    }

    parseGridLabDData(csvText) {
        const lines = csvText.split('\n');
        const data = [];
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            if (line.startsWith('#') || line === '') continue;
            
            const parts = line.split(',');
            if (parts.length >= 7) {
                // Parse complex numbers like "+2401.78+0i"
                const parseComplex = (str) => {
                    const match = str.match(/([+-]?\d*\.?\d+)([+-]?\d*\.?\d*)([ij])?/);
                    if (match) {
                        const real = parseFloat(match[1]) || 0;
                        const imag = parseFloat(match[2]) || 0;
                        return { real, imag, magnitude: Math.sqrt(real*real + imag*imag) };
                    }
                    return { real: 0, imag: 0, magnitude: 0 };
                };
                
                const timestamp = new Date(parts[0]);
                const voltageA = parseComplex(parts[1]);
                const powerA = parseComplex(parts[2]);
                const voltageB = parseComplex(parts[3]);
                const powerB = parseComplex(parts[4]);
                const voltageC = parseComplex(parts[5]);
                const powerC = parseComplex(parts[6]);
                
                data.push({
                    timestamp,
                    voltages: {
                        A: voltageA,
                        B: voltageB,
                        C: voltageC
                    },
                    powers: {
                        A: powerA,
                        B: powerB,
                        C: powerC
                    }
                });
            }
        }
        
        return data;
    }

    parseGridPackData(csvText) {
        const lines = csvText.split('\n');
        const data = [];
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            if (line === '' || !line.includes('Time (s):')) continue;
            
            // Parse time
            const timeMatch = line.match(/Time \(s\): (\d+)/);
            if (timeMatch) {
                const time = parseInt(timeMatch[1]);
                
                // Look for voltage data in next lines
                let voltageData = null;
                for (let j = i + 1; j < Math.min(i + 5, lines.length); j++) {
                    const nextLine = lines[j];
                    if (nextLine.includes('Updated Vv by GridPACK')) {
                        const vMatch = nextLine.match(/Va: \(([^)]+)\) Vb: \(([^)]+)\) Vc: \(([^)]+)\)/);
                        if (vMatch) {
                            const parseVoltage = (str) => {
                                const parts = str.split(',');
                                const real = parseFloat(parts[0]);
                                const imag = parseFloat(parts[1]);
                                return { real, imag, magnitude: Math.sqrt(real*real + imag*imag) };
                            };
                            
                            voltageData = {
                                A: parseVoltage(vMatch[1]),
                                B: parseVoltage(vMatch[2]),
                                C: parseVoltage(vMatch[3])
                            };
                        }
                        break;
                    }
                }
                
                if (voltageData) {
                    data.push({
                        time,
                        voltages: voltageData
                    });
                }
            }
        }
        
        return data;
    }

    parseRegulatorData(csvText) {
        const lines = csvText.split('\n');
        const data = [];
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            if (line.startsWith('#') || line === '') continue;
            
            const parts = line.split(',');
            if (parts.length >= 11) {
                const timestamp = new Date(parts[0]);
                
                data.push({
                    timestamp,
                    taps: {
                        A: parseInt(parts[1]),
                        B: parseInt(parts[2]),
                        C: parseInt(parts[3])
                    },
                    powerIn: {
                        A: { real: parseFloat(parts[4]), imag: parseFloat(parts[5]) },
                        B: { real: parseFloat(parts[6]), imag: parseFloat(parts[7]) },
                        C: { real: parseFloat(parts[8]), imag: parseFloat(parts[9]) },
                        total: { real: parseFloat(parts[10]), imag: parseFloat(parts[11]) }
                    }
                });
            }
        }
        
        return data;
    }

    // Enhanced timeline chart with simulation data
    async createTimelineChart() {
        if (typeof Chart === 'undefined') {
            console.warn('Chart.js not available');
            return;
        }

        const timelineCanvas = document.getElementById('timelineChart');
        if (!timelineCanvas) {
            console.warn('Timeline canvas not found');
            return;
        }

        const ctx = timelineCanvas.getContext('2d');
        
        if (this.charts.timeline) this.charts.timeline.destroy();

        // Load simulation data
        console.log('📊 Loading simulation data...');
        const simulationData = await this.loadSimulationData();

        // Prepare timeline data (attacks)
        const timelineData = this.prepareTimelineData();
        
        console.log('Creating enhanced timeline chart with simulation data');
        
        if (!timelineData.datasets || timelineData.datasets.length === 0) {
            console.warn('No attack timeline data available');
        }

        // Add simulation data to the chart
        const enhancedDatasets = [...timelineData.datasets];
        
        // Add GridLAB-D voltage data
        if (simulationData.gridlabd && simulationData.gridlabd.length > 0) {
            const voltageDataA = simulationData.gridlabd.map((point, index) => ({
                x: index, // Use array index as time for now
                y: point.voltages.A.magnitude / 1000 // Convert to kV
            }));
            
            enhancedDatasets.push({
                label: 'GridLAB-D Voltage A (kV)',
                type: 'line',
                data: voltageDataA,
                borderColor: 'rgba(76, 175, 80, 0.8)',
                backgroundColor: 'rgba(76, 175, 80, 0.1)',
                fill: false,
                tension: 0.3,
                pointRadius: 2,
                pointHoverRadius: 5
            });
        }

        // Add GridPACK voltage data
        if (simulationData.gridpack && simulationData.gridpack.length > 0) {
            const gridpackVoltageA = simulationData.gridpack.map(point => ({
                x: point.time,
                y: point.voltages.A.magnitude
            }));
            
            enhancedDatasets.push({
                label: 'GridPACK Voltage A (pu)',
                type: 'line',
                data: gridpackVoltageA,
                borderColor: 'rgba(156, 39, 176, 0.8)',
                backgroundColor: 'rgba(156, 39, 176, 0.1)',
                fill: false,
                tension: 0.3,
                pointRadius: 2,
                pointHoverRadius: 5
            });
        }

        // Add Regulator tap positions
        if (simulationData.regulator && simulationData.regulator.length > 0) {
            const tapDataA = simulationData.regulator.map((point, index) => ({
                x: index,
                y: point.taps.A
            }));
            
            enhancedDatasets.push({
                label: 'Regulator Tap A',
                type: 'line',
                data: tapDataA,
                borderColor: 'rgba(255, 152, 0, 0.8)',
                backgroundColor: 'rgba(255, 152, 0, 0.1)',
                fill: false,
                tension: 0.1,
                pointRadius: 3,
                pointHoverRadius: 6,
                yAxisID: 'y1'
            });
        }

        // Create the chart with multiple y-axes
        this.charts.timeline = new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: enhancedDatasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'nearest'
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Grid Simulation Timeline with Attack Events',
                        color: 'white',
                        font: {
                            size: 16,
                            weight: 'bold'
                        }
                    },
                    legend: {
                        display: true,
                        labels: {
                            color: 'white',
                            usePointStyle: true,
                            font: {
                                size: 12
                            }
                        }
                    },
                    tooltip: {
                        mode: 'nearest',
                        intersect: false,
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: 'white',
                        bodyColor: 'white',
                        borderColor: 'rgba(255, 255, 255, 0.3)',
                        borderWidth: 1,
                        callbacks: {
                            title: (context) => {
                                if (context.length > 0) {
                                    const dataIndex = context[0].dataIndex;
                                    const dataset = context[0].dataset;
                                    
                                    // Show attack details for attack markers
                                    if (dataset.label && dataset.label.includes('Attack')) {
                                        const attack = timelineData.attacks.find(a => 
                                            Math.abs(a.timeOffset - context[0].parsed.x) < 1
                                        );
                                        if (attack) {
                                            return `${attack.technique} at ${attack.timeOffset.toFixed(1)}s`;
                                        }
                                    }
                                    
                                    return `Time: ${context[0].parsed.x.toFixed(1)}s`;
                                }
                                return '';
                            },
                            label: (context) => {
                                const label = context.dataset.label || '';
                                const value = context.parsed.y;
                                
                                if (label.includes('Voltage')) {
                                    return `${label}: ${value.toFixed(3)}`;
                                } else if (label.includes('Tap')) {
                                    return `${label}: ${Math.round(value)}`;
                                } else if (label.includes('Attack')) {
                                    return `${label}: Impact ${value.toFixed(6)}`;
                                }
                                
                                return `${label}: ${value.toFixed(3)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        position: 'bottom',
                        title: {
                            display: true,
                            text: 'Time (seconds)',
                            color: 'white',
                            font: {
                                size: 14,
                                weight: 'bold'
                            }
                        },
                        ticks: {
                            color: 'white',
                            font: {
                                size: 12
                            }
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.2)',
                            lineWidth: 1
                        }
                    },
                    y: {
                        type: 'linear',
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Grid Parameters (Voltage, Impact)',
                            color: 'white',
                            font: {
                                size: 14,
                                weight: 'bold'
                            }
                        },
                        ticks: {
                            color: 'white',
                            font: {
                                size: 12
                            }
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.2)',
                            lineWidth: 1
                        }
                    },
                    y1: {
                        type: 'linear',
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Tap Positions',
                            color: 'white',
                            font: {
                                size: 14,
                                weight: 'bold'
                            }
                        },
                        ticks: {
                            color: 'white',
                            font: {
                                size: 12
                            }
                        },
                        grid: {
                            drawOnChartArea: false,
                            color: 'rgba(255, 255, 255, 0.2)'
                        }
                    }
                }
            }
        });

        console.log('✅ Enhanced timeline chart created with', enhancedDatasets.length, 'datasets');
    }
    createDebugChart() {
        const timelineCanvas = document.getElementById('timelineChart');
        if (!timelineCanvas) return;

        const ctx = timelineCanvas.getContext('2d');
        
        console.log('Creating debug chart...');
        
        // Simple test chart
        new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Test Points',
                    data: [
                        { x: 10, y: 1 },
                        { x: 20, y: 2 },
                        { x: 30, y: 1.5 },
                        { x: 40, y: 3 }
                    ],
                    backgroundColor: 'rgba(255, 107, 53, 0.8)',
                    borderColor: 'rgba(255, 107, 53, 1)',
                    pointRadius: 8
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Debug Chart - Chart.js Working',
                        color: 'white'
                    },
                    legend: { labels: { color: 'white' } }
                },
                scales: {
                    x: {
                        type: 'linear',
                        title: { display: true, text: 'Time (seconds)', color: 'white' },
                        ticks: { color: 'white' },
                        grid: { color: 'rgba(255,255,255,0.2)' }
                    },
                    y: {
                        title: { display: true, text: 'Test Values', color: 'white' },
                        ticks: { color: 'white' },
                        grid: { color: 'rgba(255,255,255,0.2)' }
                    }
                }
            }
        });
    }
}

// Initialize the app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Initializing Attack Visualizer...');
    window.attackVisualizer = new AttackVisualizer();
    console.log('✅ Attack Visualizer initialized');
    
    // Add debug function to window for testing
    window.debugChart = () => {
        window.attackVisualizer.createDebugChart();
    };
    
    // Add manual chart creation function for testing
    window.createChart = () => {
        if (window.attackVisualizer && window.attackVisualizer.currentData) {
            window.attackVisualizer.createTimelineChart();
        } else {
            console.log('No data loaded yet');
        }
    };
});