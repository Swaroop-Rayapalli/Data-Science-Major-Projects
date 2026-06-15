document.getElementById('heartForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const btn = e.target.querySelector('button');
    btn.textContent = "Processing...";
    btn.disabled = true;

    const data = {
        age: parseFloat(document.getElementById('age').value),
        sex: parseFloat(document.getElementById('sex').value),
        cp: parseFloat(document.getElementById('cp').value),
        trestbps: parseFloat(document.getElementById('trestbps').value),
        chol: parseFloat(document.getElementById('chol').value),
        fbs: parseFloat(document.getElementById('fbs').value),
        restecg: parseFloat(document.getElementById('restecg').value),
        thalach: parseFloat(document.getElementById('thalach').value),
        exang: parseFloat(document.getElementById('exang').value),
        oldpeak: parseFloat(document.getElementById('oldpeak').value),
        slope: parseFloat(document.getElementById('slope').value),
        ca: parseFloat(document.getElementById('ca').value),
        thal: parseFloat(document.getElementById('thal').value)
    };

    try {
        const response = await fetch('/api/heart/predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();

        const box = document.getElementById('resultBox');
        box.style.display = 'block';
        box.className = 'result-box ' + (result.risk === 'High Risk' ? 'high-risk' : 'low-risk');

        document.getElementById('resultText').textContent = result.risk;
        document.getElementById('probabilityText').textContent = `Probability: ${result.probability}%`;
        document.getElementById('predId').textContent = result.prediction_id;

    } catch (err) {
        alert("Error making prediction: " + err);
    } finally {
        btn.textContent = "Predict Risk";
        btn.disabled = false;
    }
});
