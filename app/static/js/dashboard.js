document.addEventListener('DOMContentLoaded', async () => {
  try {
    const res = await fetch('/api/analytics/metrics');
    if (!res.ok) {
      console.error("Error al cargar métricas");
      return;
    }
    const data = await res.json();
    renderKPIs(data.kpis);
    renderCharts(data);
  } catch (err) {
    console.error("Error al obtener datos analíticos:", err);
  }
});

function renderKPIs(kpis) {
  if (!kpis) return;
  document.getElementById('kpi-total-records').textContent = kpis.total_records.toLocaleString();
  document.getElementById('kpi-total-graves').textContent = kpis.total_graves.toLocaleString();
  document.getElementById('kpi-total-recuperados').textContent = kpis.total_recuperados.toLocaleString();
  document.getElementById('kpi-total-defunciones').textContent = kpis.total_defunciones.toLocaleString();
}

function renderCharts(data) {
  // 1. Curva por Semana Epidemiológica
  const ctxSemanas = document.getElementById('chartSemanas');
  if (ctxSemanas && data.distribucion_semanal) {
    const labels = data.distribucion_semanal.map(d => d.semana);
    const values = data.distribucion_semanal.map(d => d.total);

    new Chart(ctxSemanas, {
      type: 'line',
      data: {
        labels: labels.length ? labels : ['Sin datos'],
        datasets: [{
          label: 'Eventos Notificados',
          data: values.length ? values : [0],
          borderColor: '#008B9E',
          backgroundColor: 'rgba(23, 184, 190, 0.15)',
          fill: true,
          tension: 0.35,
          pointRadius: 4,
          pointBackgroundColor: '#0A2540',
          pointBorderColor: '#17B8BE',
          pointHoverRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { precision: 0, color: '#64748B' },
            grid: { color: '#E2E8F0' }
          },
          x: {
            ticks: { color: '#64748B' },
            grid: { display: false }
          }
        }
      }
    });
  }

  // 2. Top Vacunas (Doughnut)
  const ctxVacunas = document.getElementById('chartVacunas');
  if (ctxVacunas && data.top_vacunas) {
    const labels = data.top_vacunas.map(v => v.vacuna);
    const values = data.top_vacunas.map(v => v.total);
    const colors = [
      '#0A2540', '#008B9E', '#17B8BE', '#0284c7', '#0d9488',
      '#f59e0b', '#10b981', '#6366f1', '#64748B', '#f43f5e'
    ];

    new Chart(ctxVacunas, {
      type: 'doughnut',
      data: {
        labels: labels.length ? labels : ['Sin datos'],
        datasets: [{
          data: values.length ? values : [1],
          backgroundColor: labels.length ? colors.slice(0, labels.length) : ['#E2E8F0'],
          borderColor: '#FFFFFF',
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              boxWidth: 12,
              font: { size: 11 },
              color: '#0A2540'
            }
          }
        }
      }
    });
  }

  // 3. Grupos de Edad (Bar)
  const ctxEdades = document.getElementById('chartEdades');
  if (ctxEdades && data.distribucion_edad) {
    const labels = data.distribucion_edad.map(e => e.label);
    const values = data.distribucion_edad.map(e => e.total);

    new Chart(ctxEdades, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Casos',
          data: values,
          backgroundColor: '#17B8BE',
          hoverBackgroundColor: '#008B9E',
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
          y: {
            beginAtZero: true,
            ticks: { precision: 0, color: '#64748B' },
            grid: { color: '#E2E8F0' }
          },
          x: {
            ticks: { color: '#64748B' },
            grid: { display: false }
          }
        }
      }
    });
  }

  // 4. Regiones Sanitarias de Hidalgo (Horizontal Bar)
  const ctxRegiones = document.getElementById('chartRegiones');
  if (ctxRegiones && data.distribucion_regiones) {
    const labels = data.distribucion_regiones.map(r => r.region);
    const values = data.distribucion_regiones.map(r => r.total);

    new Chart(ctxRegiones, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Casos por Región Sanitaria',
          data: values,
          backgroundColor: '#008B9E',
          hoverBackgroundColor: '#0A2540',
          borderRadius: 6
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: {
            beginAtZero: true,
            ticks: { precision: 0, color: '#64748B' },
            grid: { color: '#E2E8F0' }
          },
          y: {
            ticks: {
              font: { size: 10 },
              color: '#0A2540'
            },
            grid: { display: false }
          }
        }
      }
    });
  }
}
