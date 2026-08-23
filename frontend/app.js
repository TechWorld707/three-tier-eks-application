document.querySelector('#profile-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const result = document.querySelector('#result');
  try {
    const response = await fetch('/api/submissions', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(Object.fromEntries(new FormData(event.target)))
    });
    const body = await response.json();
    result.textContent = response.ok ? `Saved. Reference: ${body.id}` : body.errors.join(' ');
    if (response.ok) event.target.reset();
  } catch (_) { result.textContent = 'The service is temporarily unavailable.'; }
});
