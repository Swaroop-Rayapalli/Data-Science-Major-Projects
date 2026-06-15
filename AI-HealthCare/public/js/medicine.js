document.getElementById('forecastForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const btn = e.target.querySelector('button');
    btn.textContent = "Forecasting...";
    btn.disabled = true;

    const data = {
        medicine_name: document.getElementById('medicine').value,
        periods: parseInt(document.getElementById('periods').value),
        current_stock: parseInt(document.getElementById('stock').value)
    };

    try {
        const response = await fetch('/api/medicine/forecast', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();

        document.getElementById('dashboard').style.display = 'block';
        document.getElementById('totalDemand').textContent = result.total_predicted_demand;
        document.getElementById('recommendation').textContent = result.recommendation;
        document.getElementById('predId').textContent = result.forecast_id;

        // Plotly Chart
        const trace = {
            x: result.chart_data.dates,
            y: result.chart_data.values,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Predicted Demand',
            line: { color: '#8b5cf6', width: 3 },
            marker: { size: 6 }
        };

        const layout = {
            title: 'Predicted Daily Demand',
            paper_bgcolor: 'white',
            plot_bgcolor: '#f8fafc',
            margin: { t: 40, r: 20, l: 40, b: 40 },
            xaxis: { gridcolor: '#e2e8f0' },
            yaxis: { gridcolor: '#e2e8f0' }
        };

        Plotly.newPlot('chart', [trace], layout, { responsive: true });

    } catch (err) {
        alert("Error generating forecast: " + err);
    } finally {
        btn.textContent = "Generate Forecast";
        btn.disabled = false;
    }
});
