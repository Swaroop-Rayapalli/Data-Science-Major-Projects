// ── Real-time polling interval (ms)
const REALTIME_INTERVAL = 5000;
let realtimeTimer = null;

// Global state for charts and configuration
const state = {
    charts: {
        churnPie: null,
        propertyBar: null,
        pbiUsage: null,
        pbiProducts: null,
        salesForecast: null
    },
    uploadedFile: null
};

// Initialize App
document.addEventListener("DOMContentLoaded", () => {
    initNavigation();
    initForms();
    initDragAndDrop();
    fetchConfig();
    updateDashboardStats();
    startRealtimePolling();

    // Set current date
    const dateOpts = { year: 'numeric', month: 'long', day: 'numeric' };
    document.getElementById("current-date").textContent = new Date().toLocaleDateString("en-US", dateOpts);

    // Inject LIVE indicator into the header next to the date
    injectLiveIndicator();
});

// Inject a blinking LIVE badge + last-updated clock into the page header
function injectLiveIndicator() {
    const dateEl = document.getElementById("current-date");
    if (!dateEl) return;

    // Build the badge HTML
    const badge = document.createElement("span");
    badge.id = "live-badge";
    badge.style.cssText = [
        "display:inline-flex",
        "align-items:center",
        "gap:6px",
        "margin-left:14px",
        "font-size:11px",
        "font-weight:600",
        "letter-spacing:0.08em",
        "color:hsl(172,90%,46%)",
        "vertical-align:middle"
    ].join(";");

    badge.innerHTML = `
        <span id="live-dot" style="
            display:inline-block;
            width:8px;height:8px;
            border-radius:50%;
            background:hsl(172,90%,46%);
            box-shadow:0 0 6px hsl(172,90%,46%);
            animation:livePulse 1.4s ease-in-out infinite;
        "></span>
        LIVE &nbsp;·&nbsp;
        <span id="live-last-updated" style="color:hsl(215,15%,60%);font-weight:400;">updating...</span>
    `;
    dateEl.after(badge);

    // Inject keyframe animation once
    if (!document.getElementById("live-pulse-style")) {
        const style = document.createElement("style");
        style.id = "live-pulse-style";
        style.textContent = `
            @keyframes livePulse {
                0%,100%{opacity:1;transform:scale(1);}
                50%{opacity:0.35;transform:scale(0.7);}
            }
        `;
        document.head.appendChild(style);
    }
}

// Update the "last updated" text shown next to the LIVE dot
function touchLiveTimestamp() {
    const el = document.getElementById("live-last-updated");
    if (!el) return;
    const now = new Date();
    const h = String(now.getHours()).padStart(2, "0");
    const m = String(now.getMinutes()).padStart(2, "0");
    const s = String(now.getSeconds()).padStart(2, "0");
    el.textContent = `last sync ${h}:${m}:${s}`;
}

// Start (or restart) the real-time polling loop
function startRealtimePolling() {
    if (realtimeTimer) clearInterval(realtimeTimer);
    realtimeTimer = setInterval(async () => {
        await updateDashboardStats();
        touchLiveTimestamp();
    }, REALTIME_INTERVAL);
    console.log(`[Smart BI] Real-time polling started — refreshing every ${REALTIME_INTERVAL / 1000}s`);
}

// 1. SPA Tab Navigation
function initNavigation() {
    const navItems = document.querySelectorAll(".nav-item");
    const tabPanes = document.querySelectorAll(".tab-pane");
    const pageTitle = document.getElementById("page-title");
    const pageSubtitle = document.getElementById("page-subtitle");

    const titles = {
        home: { title: "Executive Suite Overview", subtitle: "End-to-End Decision Support System" },
        churn: { title: "Customer Churn Prediction", subtitle: "Predictive subscriber retention analysis" },
        sales: { title: "Revenue Forecasting", subtitle: "Time-series sales intelligence & modeling" },
        recommend: { title: "Movie Recommendation Engine", subtitle: "Collaborative filtering · Discover films you'll love" },
        property: { title: "Market & Property Intelligence", subtitle: "Machine learning real estate valuation" },
        executive: { title: "Executive Analytics Board", subtitle: "Live Business Intelligence Dashboard" }
    };

    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const tabId = item.getAttribute("data-tab");
            
            // Toggle sidebar active classes
            navItems.forEach(nav => nav.classList.remove("active"));
            item.classList.add("active");
            
            // Toggle tab content display
            tabPanes.forEach(pane => pane.classList.remove("active"));
            document.getElementById(`tab-${tabId}`).classList.add("active");
            
            // Update Headers
            const t = titles[tabId];
            if (t) {
                pageTitle.textContent = t.title;
                pageSubtitle.textContent = t.subtitle;
            }
            
            // Trigger chart resize if navigating back to charts
            if (tabId === 'home' || tabId === 'executive') {
                setTimeout(resizeCharts, 50);
            }
        });
    });
}

// Helper to force Chart.js charts to redraw and fit their container
function resizeCharts() {
    Object.values(state.charts).forEach(chart => {
        if (chart) {
            chart.resize();
            chart.update();
        }
    });
}

// 2. Fetch System & Database configuration from backend
async function fetchConfig() {
    try {
        const response = await fetch("/api/config");
        if (response.ok) {
            const data = await response.json();
            document.getElementById("sidebar-db-status").textContent = `DB: ${data.db_status}`;
        }
    } catch (err) {
        console.error("Error fetching database configuration:", err);
    }
}

// Helper: Make API calls to local Flask endpoints
async function callApi(key, options) {
    const endpoints = {
        churn:     "/api/predict-churn",
        sales:     "/api/forecast",
        recommend: "/api/recommend",
        property:  "/api/predict-price"
    };
    const url = endpoints[key];
    const response = await fetch(url, options);
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
    }
    return response.json();
}

// 4. ML Forms Logic
function initForms() {
    // A. Churn Form
    const formChurn = document.getElementById("form-churn");
    const churnPlaceholder = document.getElementById("churn-result-placeholder");
    const churnContent = document.getElementById("churn-result-content");
    const btnChurn = document.getElementById("btn-predict-churn");

    formChurn.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        // Show loading state
        btnChurn.disabled = true;
        btnChurn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Running assessment model...';
        churnPlaceholder.classList.add("hide");
        churnContent.classList.add("hide");

        const payload = {
            gender: document.getElementById("churn-gender").value,
            tenure: parseInt(document.getElementById("churn-tenure").value),
            MonthlyCharges: parseFloat(document.getElementById("churn-monthly").value),
            Contract: document.getElementById("churn-contract").value,
            InternetService: document.getElementById("churn-internet").value
        };

        try {
            const result = await callApi("churn", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            // Populate Churn Dial Gauge
            const probPct = Math.round(result.probability * 100);
            document.getElementById("churn-result-pct").textContent = `${probPct}%`;
            document.getElementById("churn-result-prob").textContent = `${probPct}%`;
            document.getElementById("churn-result-label").textContent = result.prediction;
            
            // Animate SVG circular gauge
            const circle = document.getElementById("churn-gauge-fill");
            const circumference = 2 * Math.PI * 45; // 282.74
            const offset = circumference - (result.probability * circumference);
            circle.style.strokeDashoffset = offset;
            
            // Style badge and alert according to risk
            const badge = document.getElementById("churn-result-label");
            const alertBanner = document.getElementById("churn-alert-banner");
            const alertTitle = document.getElementById("churn-alert-title");
            
            if (result.prediction === "Churn" || result.probability >= 0.5) {
                badge.className = "value badge badge-purple";
                alertBanner.className = "alert-banner";
                alertTitle.textContent = "High Risk Customer Profile";
                circle.style.stroke = "hsl(355, 85%, 52%)"; // Red glow
            } else {
                badge.className = "value badge badge-green";
                alertBanner.className = "alert-banner low-risk";
                alertTitle.textContent = "Stable Customer Account";
                circle.style.stroke = "hsl(172, 90%, 46%)"; // Teal glow
            }

            churnContent.classList.remove("hide");
            updateDashboardStats(); // Refresh DB dashboard figures immediately
        } catch (err) {
            alert(`Churn Evaluation Failed: ${err.message}`);
            churnPlaceholder.classList.remove("hide");
        } finally {
            btnChurn.disabled = false;
            btnChurn.innerHTML = '<i class="fa-solid fa-brain"></i> Predict Churn Probability';
        }
    });

    // B. Property Insights Form
    const formProperty = document.getElementById("form-property");
    const propertyPlaceholder = document.getElementById("property-result-placeholder");
    const propertyContent = document.getElementById("property-result-content");
    const btnProperty = document.getElementById("form-property").querySelector("button[type='submit']");

    formProperty.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        btnProperty.disabled = true;
        btnProperty.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Estimating valuation...';
        propertyPlaceholder.classList.add("hide");
        propertyContent.classList.add("hide");

        const area = parseFloat(document.getElementById("property-area").value);
        const bedrooms = parseInt(document.getElementById("property-bedrooms").value);
        const bathrooms = parseInt(document.getElementById("property-bathrooms").value);
        const location = document.getElementById("property-location").value;

        const payload = { area, bedrooms, bathrooms, location };

        try {
            const result = await callApi("property", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            // Animate currency display counter
            const formatted = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(result.price);
            document.getElementById("property-price-value").textContent = formatted;
            
            // Calculate and output breakdown values
            const ratePerSqFt = Math.round(result.price / area);
            document.getElementById("property-breakdown-rate").textContent = `₹${ratePerSqFt.toLocaleString('en-IN')} / sq ft`;
            document.getElementById("property-breakdown-config").textContent = `${bedrooms} BHK (${bathrooms} Bath)`;
            
            const locLabel = document.getElementById("property-location").options[document.getElementById("property-location").selectedIndex].text;
            document.getElementById("property-breakdown-location").textContent = locLabel.split(" (")[0];

            propertyContent.classList.remove("hide");
            updateDashboardStats();
        } catch (err) {
            alert(`Property Valuation Failed: ${err.message}`);
            propertyPlaceholder.classList.remove("hide");
        } finally {
            btnProperty.disabled = false;
            btnProperty.innerHTML = '<i class="fa-solid fa-coins"></i> Estimate Fair Market Price';
        }
    });

    // C. Movie Recommendation Form
    const btnRec  = document.getElementById("btn-generate-rec");
    const gridRec = document.getElementById("recommendations-grid");

    btnRec.addEventListener("click", async () => {
        const genre    = document.getElementById("rec-genre").value;
        const mood     = document.getElementById("rec-mood").value;
        const era      = document.getElementById("rec-era").value;
        const language = document.getElementById("rec-lang").value;

        const langFlags = { english:"🇬🇧", hindi:"🇮🇳", telugu:"🎬", korean:"🇰🇷", japanese:"🇯🇵", french:"🇫🇷", spanish:"🇪🇸", german:"🇩🇪", italian:"🇮🇹" };
        const langFlag  = langFlags[language] || "🌍";

        btnRec.disabled = true;
        btnRec.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Finding movies...';
        gridRec.innerHTML = `
            <div class="rec-card placeholder">
                <div class="rec-icon"><i class="fa-solid fa-rotate fa-spin"></i></div>
                <div class="rec-title">Analysing your preferences...</div>
                <div class="rec-category">${langFlag} ${language.charAt(0).toUpperCase()+language.slice(1)} · ${genre} · ${era} films</div>
            </div>
        `;

        try {
            const result = await callApi("recommend", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ genre, mood, era, language })
            });

            gridRec.innerHTML = "";

            // Update seed badge
            const seedBadge = document.getElementById("rec-seed-badge");
            if (result.seed_movie) {
                seedBadge.textContent = `${langFlag} Based on: "${result.seed_movie}"`;
            }

            // Rotate through film-themed icons
            const icons   = ["fa-film", "fa-clapperboard", "fa-star", "fa-ticket", "fa-video"];
            const badges  = ["Top Pick", "Trending", "Critically Acclaimed", "Fan Favourite", "Hidden Gem"];
            const moodEmoji = { exciting:"⚡", "feel-good":"😊", emotional:"💧", scary:"😱", thoughtful:"🤔" };
            const moodLabel = moodEmoji[mood] || "🎬";

            result.recommendations.forEach((movie, index) => {
                const icon   = icons[index % icons.length];
                const badge  = badges[index % badges.length];
                const title  = typeof movie === "object" ? movie.title  : movie;
                const genre  = typeof movie === "object" ? movie.genre  : "Film";
                const score  = typeof movie === "object" ? movie.score  : (94 - index * 2);

                const card = document.createElement("div");
                card.className = "rec-card";
                card.innerHTML = `
                    <div class="rec-icon"><i class="fa-solid ${icon}"></i></div>
                    <div class="rec-title">${title}</div>
                    <div class="rec-category">${genre}</div>
                    <div class="rec-footer">
                        <span>${moodLabel} ${badge}</span>
                        <span>Match: ${score}%</span>
                    </div>
                `;
                gridRec.appendChild(card);
            });

            updateDashboardStats();
        } catch (err) {
            alert(`Recommendation Failed: ${err.message}`);
            gridRec.innerHTML = `
                <div class="rec-card placeholder">
                    <div class="rec-icon"><i class="fa-solid fa-circle-exclamation"></i></div>
                    <div class="rec-title">Recommendation Failed</div>
                    <div class="rec-category">${err.message}</div>
                </div>
            `;
        } finally {
            btnRec.disabled = false;
            btnRec.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Find My Movies';
        }
    });
}

// 5. Drag-and-Drop and CSV upload for sales forecasting
function initDragAndDrop() {
    const dropZone = document.getElementById("csv-drop-zone");
    const fileInput = document.getElementById("csv-file-input");
    const fileDetails = document.getElementById("upload-file-details");
    const fileName = document.getElementById("selected-file-name");
    const btnClear = document.getElementById("btn-clear-file");
    const btnLoadDemo = document.getElementById("btn-load-demo-csv");
    const btnForecast = document.getElementById("btn-run-forecast");

    // Open browse dialog on click
    dropZone.addEventListener("click", (e) => {
        if (e.target.closest("#btn-clear-file") || e.target.closest(".file-details")) return;
        fileInput.click();
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleSelectedFile(e.target.files[0]);
        }
    });

    // Drag over styling
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    ["dragleave", "dragend"].forEach(type => {
        dropZone.addEventListener(type, () => {
            dropZone.classList.remove("dragover");
        });
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            handleSelectedFile(e.dataTransfer.files[0]);
        }
    });

    btnClear.addEventListener("click", () => {
        state.uploadedFile = null;
        fileInput.value = "";
        fileDetails.classList.add("hide");
        dropZone.querySelector(".upload-icon").style.display = "block";
        dropZone.querySelector(".drop-text").style.display = "block";
    });

    btnLoadDemo.addEventListener("click", () => {
        state.uploadedFile = "demo";
        fileName.textContent = "sample_historical_sales.csv (Demo Loaded)";
        fileDetails.classList.remove("hide");
        dropZone.querySelector(".upload-icon").style.display = "none";
        dropZone.querySelector(".drop-text").style.display = "none";
    });

    btnForecast.addEventListener("click", async () => {
        const periods = parseInt(document.getElementById("sales-periods").value) || 90;
        
        btnForecast.disabled = true;
        btnForecast.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Querying Prophet forecast engine...';

        try {
            let result;
            if (state.uploadedFile && state.uploadedFile !== "demo") {
                // Real file upload — must use FormData/multipart
                const formData = new FormData();
                formData.append("periods", periods);
                formData.append("file", state.uploadedFile);
                result = await callApi("sales", { method: "POST", body: formData });
            } else {
                // No file — send plain JSON (avoids multipart parsing issues)
                result = await callApi("sales", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ periods })
                });
            }

            // Display results chart and KPIs
            document.getElementById("sales-result-container").classList.remove("hide");
            
            // Format total revenue KPI badge
            const totalRevFormatted = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(result.summary.total_sales);
            document.getElementById("sales-forecast-kpi-total").textContent = `Forecasted Total: ${totalRevFormatted}`;
            
            const growthBadge = document.getElementById("sales-forecast-kpi-growth");
            growthBadge.textContent = `${result.summary.growth_rate_pct >= 0 ? '+' : ''}${result.summary.growth_rate_pct}% growth`;
            if (result.summary.growth_rate_pct >= 0) {
                growthBadge.className = "badge badge-green";
            } else {
                growthBadge.className = "badge badge-danger";
            }
            
            // Build Forecast Chart
            renderForecastChart(result.forecast);
            updateDashboardStats();
        } catch (err) {
            alert(`Sales Forecasting Failed: ${err.message}`);
        } finally {
            btnForecast.disabled = false;
            btnForecast.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Forecast Future Sales';
        }
    });

    function handleSelectedFile(file) {
        if (file.type !== "text/csv" && !file.name.endsWith(".csv")) {
            alert("Please upload a valid CSV file containing columns 'ds' and 'y'.");
            return;
        }
        state.uploadedFile = file;
        fileName.textContent = `${file.name} (${Math.round(file.size / 1024)} KB)`;
        fileDetails.classList.remove("hide");
        dropZone.querySelector(".upload-icon").style.display = "none";
        dropZone.querySelector(".drop-text").style.display = "none";
    }
}

// 6. Draw Forecasting Charts using Chart.js
function renderForecastChart(forecastData) {
    const ctx = document.getElementById("chart-sales-forecast").getContext("2d");
    
    // Destroy previous chart if it exists
    if (state.charts.salesForecast) {
        state.charts.salesForecast.destroy();
    }
    
    // Limit displaying labels for readability if dataset is large
    const step = Math.ceil(forecastData.length / 15);
    const labels = forecastData.map((d, index) => index % step === 0 ? d.ds : "");
    const sales  = forecastData.map(d => d.sales);
    const yhats  = forecastData.map(d => d.yhat);
    
    state.charts.salesForecast = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Forecasted Daily Sales (₹)',
                    data: sales,
                    borderColor: 'hsl(172, 90%, 46%)',
                    backgroundColor: 'rgba(0, 240, 200, 0.07)',
                    borderWidth: 2.5,
                    pointRadius: 1.5,
                    tension: 0.35,
                    fill: true,
                    order: 1
                },
                {
                    label: 'Prophet Trend (yhat)',
                    data: yhats,
                    borderColor: 'hsl(260, 80%, 70%)',
                    backgroundColor: 'transparent',
                    borderWidth: 1.5,
                    borderDash: [5, 4],
                    pointRadius: 0,
                    tension: 0.4,
                    fill: false,
                    order: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    labels: { color: 'hsl(215, 15%, 70%)', font: { family: 'Outfit', size: 12 } }
                },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            const val = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(ctx.raw);
                            return ` ${ctx.dataset.label}: ${val}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: 'hsl(215, 15%, 50%)', font: { size: 10 } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.04)' },
                    ticks: {
                        color: 'hsl(215, 15%, 50%)',
                        font: { size: 10 },
                        callback: val => `₹${(val/1000).toFixed(0)}K`
                    }
                }
            }
        }
    });
}


// 7. Update Dashboard Stats (Retrieve Aggregations from DB Logs)
async function updateDashboardStats() {
    try {
        const stats = await fetch("/api/dashboard-stats").then(res => res.json());
        
        // A. Update Overview KPI Cards
        const revenueFormatted = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(stats.kpis.forecast_revenue);
        document.getElementById("kpi-revenue").textContent = revenueFormatted;
        document.getElementById("kpi-churn").textContent = stats.kpis.customers_at_risk;
        document.getElementById("kpi-recommendations").textContent = stats.kpis.recommendations_generated;
        document.getElementById("kpi-properties").textContent = stats.kpis.properties_evaluated;

        // B. Update Executive / Power BI Fallback KPI Dashboard numbers
        document.getElementById("pbi-val-total").textContent = stats.kpis.total_churn_evals + stats.kpis.properties_evaluated + stats.kpis.recommendations_generated;
        
        const avgPropLakhs = (stats.kpis.avg_property_value / 100000).toFixed(1);
        document.getElementById("pbi-val-prop").textContent = `₹${avgPropLakhs}L`;
        
        const churnRate = stats.kpis.total_churn_evals > 0 ? Math.round((stats.kpis.customers_at_risk / stats.kpis.total_churn_evals) * 100) : 0;
        document.getElementById("pbi-val-churn").textContent = `${churnRate}%`;
        
        const churnTrend = document.getElementById("pbi-val-churn-trend");
        if (churnRate > 35) {
            churnTrend.className = "pbi-trend-label text-danger";
            churnTrend.innerHTML = '<i class="fa-solid fa-arrow-trend-up"></i> Critical Risk level';
        } else {
            churnTrend.className = "pbi-trend-label text-success";
            churnTrend.innerHTML = '<i class="fa-solid fa-arrow-trend-down"></i> Under control';
        }

        // C. Draw Churn Risk Pie Chart
        renderChurnPieChart(stats.charts.churn);

        // D. Draw Property Location Bar Chart
        renderPropertyBarChart(stats.charts.properties);

        // E. Draw Service Usage & Product charts in Power BI simulation
        renderPbiCharts(stats);

        // F. Update Evaluation Logs Table
        const tbody = document.getElementById("activity-tbody");
        if (stats.recent_activity.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="no-data"><i class="fa-regular fa-folder-open"></i> No ML evaluations logged in database yet.</td></tr>';
            return;
        }

        tbody.innerHTML = "";
        stats.recent_activity.forEach(row => {
            const tr = document.createElement("tr");
            
            // Format timestamp nicely
            const timeStr = new Date(row.timestamp).toLocaleString("en-US", { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
            
            tr.innerHTML = `
                <td><strong>${row.type}</strong></td>
                <td>${timeStr}</td>
                <td><code class="code-font">${row.details}</code></td>
                <td><span class="system-badge" style="padding: 3px 8px; font-size: 11px;"><i class="fa-regular fa-circle-check"></i> Synced</span></td>
            `;
            tbody.appendChild(tr);
        });

    } catch (err) {
        console.error("Failed to load dashboard logs and stats:", err);
    }
}

// Draw Dashboard Churn Risk Pie Chart
function renderChurnPieChart(churnData) {
    const ctx = document.getElementById("chart-churn-pie").getContext("2d");
    if (state.charts.churnPie) {
        state.charts.churnPie.destroy();
    }

    const churnCount = churnData["Churn"] || 0;
    const noChurnCount = churnData["No Churn"] || 0;

    // Default placeholder visuals if empty
    const counts = (churnCount === 0 && noChurnCount === 0) ? [12, 45] : [churnCount, noChurnCount];

    state.charts.churnPie = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['At Risk (Churn)', 'Stable Customers'],
            datasets: [{
                data: counts,
                backgroundColor: ['hsl(355, 85%, 52%)', 'hsl(172, 90%, 46%)'],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: 'hsl(215, 15%, 70%)', font: { family: 'Outfit', size: 12 } }
                }
            },
            cutout: '65%'
        }
    });
}

// Draw Dashboard Property Prices Bar Chart
function renderPropertyBarChart(propData) {
    const ctx = document.getElementById("chart-property-bar").getContext("2d");
    if (state.charts.propertyBar) {
        state.charts.propertyBar.destroy();
    }

    // Default mock data if DB empty
    let labels = ["Low Class Suburban", "Suburban Medium", "Premium Sector"];
    let prices = [3500000, 8500000, 18500000];

    if (propData && propData.length > 0) {
        labels = propData.map(d => d.location.charAt(0).toUpperCase() + d.location.slice(1));
        prices = propData.map(d => d.avg_price);
    }

    state.charts.propertyBar = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Average Price (₹)',
                data: prices,
                backgroundColor: 'rgba(138, 43, 226, 0.4)',
                borderColor: 'hsl(263, 90%, 55%)',
                borderWidth: 1.5,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { grid: { display: false }, ticks: { color: 'hsl(215, 15%, 60%)' } },
                y: { grid: { color: 'rgba(255, 255, 255, 0.04)' }, ticks: { color: 'hsl(215, 15%, 60%)' } }
            }
        }
    });
}

// Draw Power BI simulated charts
function renderPbiCharts(stats) {
    // A. Usage Logs Chart
    const ctxUsage = document.getElementById("pbi-chart-usage").getContext("2d");
    if (state.charts.pbiUsage) {
        state.charts.pbiUsage.destroy();
    }
    
    state.charts.pbiUsage = new Chart(ctxUsage, {
        type: 'bar',
        data: {
            labels: ['Churn Evals', 'Property Price Evals', 'Product Recs'],
            datasets: [{
                label: 'Evaluations count',
                data: [stats.kpis.total_churn_evals, stats.kpis.properties_evaluated, stats.kpis.recommendations_generated],
                backgroundColor: ['rgba(255, 60, 80, 0.4)', 'rgba(0, 240, 200, 0.4)', 'rgba(180, 60, 255, 0.4)'],
                borderColor: ['hsl(355, 85%, 52%)', 'hsl(172, 90%, 46%)', 'hsl(263, 90%, 55%)'],
                borderWidth: 1.5,
                borderRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false }, ticks: { color: 'hsl(215, 15%, 60%)', font: { size: 10 } } },
                y: { grid: { color: 'rgba(255, 255, 255, 0.04)' }, ticks: { color: 'hsl(215, 15%, 60%)', font: { size: 10 } } }
            }
        }
    });

    // B. Recommended Products Frequency Chart
    const ctxProducts = document.getElementById("pbi-chart-products").getContext("2d");
    if (state.charts.pbiProducts) {
        state.charts.pbiProducts.destroy();
    }

    state.charts.pbiProducts = new Chart(ctxProducts, {
        type: 'bar',
        data: {
            labels: ['Laptop Pro', 'Curved Monitor', 'Office Chair', 'Keyboards', 'Mice'],
            datasets: [{
                label: 'Times Recommended',
                data: [12, 19, 8, 5, 14],
                backgroundColor: 'rgba(0, 180, 255, 0.4)',
                borderColor: 'hsl(200, 85%, 50%)',
                borderWidth: 1.5,
                borderRadius: 5
            }]
        },
        options: {
            indexAxis: 'y', // horizontal bar chart
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: 'rgba(255, 255, 255, 0.04)' }, ticks: { color: 'hsl(215, 15%, 60%)', font: { size: 10 } } },
                y: { grid: { display: false }, ticks: { color: 'hsl(215, 15%, 60%)', font: { size: 10 } } }
            }
        }
    });
}
