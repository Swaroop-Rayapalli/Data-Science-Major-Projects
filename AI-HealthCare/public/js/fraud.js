document.getElementById('fraudForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const btn = e.target.querySelector('button');
    btn.textContent = "Analyzing...";
    btn.disabled = true;

    const data = {
        claimant_name: document.getElementById('claimant').value,
        Time: parseFloat(document.getElementById('time').value),
        Amount: parseFloat(document.getElementById('amount').value)
        // V1-V28 will use defaults
    };

    try {
        const response = await fetch('/api/fraud/predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();

        const box = document.getElementById('resultBox');
        box.style.display = 'block';
        box.className = 'result-box ' + (result.status === 'Fraudulent' ? 'fraud' : 'legit');

        document.getElementById('resultText').textContent = result.status;
        document.getElementById('probabilityText').textContent = `Anomaly Score: ${result.probability}%`;
        document.getElementById('predId').textContent = result.claim_id;

    } catch (err) {
        alert("Error analyzing claim: " + err);
    } finally {
        btn.textContent = "Analyze Claim";
        btn.disabled = false;
    }
});
