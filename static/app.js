document.addEventListener('DOMContentLoaded', () => {
  const jobId = window.location.pathname.split('/').filter(Boolean).at(-1);
  if (!jobId || !document.getElementById('log-output')) return;

  const poll = () => {
    fetch(`/api/jobs/${jobId}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.logs && data.logs.length) {
          const logOutput = document.getElementById('log-output');
          logOutput.textContent = data.logs.join('\n');
        }

        const badge = document.getElementById('status-badge');
        if (badge) {
          badge.textContent = data.status;
          badge.className = `status-badge ${data.status}`;
        }

        const started = document.getElementById('started-at');
        if (started) started.textContent = data.started_at || 'pending';

        const finished = document.getElementById('finished-at');
        if (finished) finished.textContent = data.finished_at || 'pending';

        const statusText = document.getElementById('job-status-text');
        if (statusText) {
          statusText.textContent = data.status === 'completed'
            ? 'Audit completed successfully.'
            : data.status === 'failed'
              ? 'Error encountered during the audit pipeline.'
              : 'Tracking pipeline progress...';
        }

        const artifactList = document.getElementById('artifact-list');
        if (artifactList && data.artifacts && data.artifacts.length) {
          artifactList.innerHTML = data.artifacts
            .map((item) => `<a href="${item.url}" target="_blank">${item.name}</a>`)
            .join('');
        }

        if (data.status !== 'completed' && data.status !== 'failed') {
          setTimeout(poll, 2000);
        }
      })
      .catch(() => setTimeout(poll, 2000));
  };

  poll();
});
