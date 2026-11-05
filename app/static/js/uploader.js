document.addEventListener('DOMContentLoaded', () => {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const fileListContainer = document.getElementById('file-list-container');
  const fileList = document.getElementById('file-list');
  const fileCount = document.getElementById('file-count');
  const clearFilesBtn = document.getElementById('clear-files-btn');
  const uploadBtn = document.getElementById('upload-btn');
  const uploadProgress = document.getElementById('upload-progress');
  const resultsCard = document.getElementById('results-card');
  const resultsTableBody = document.getElementById('results-table-body');

  let selectedFiles = [];

  // Drag & drop events
  dropZone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('border-sky-500', 'bg-sky-50');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('border-sky-500', 'bg-sky-50');
    }, false);
  });

  dropZone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    handleNewFiles(dt.files);
  });

  fileInput.addEventListener('change', (e) => {
    handleNewFiles(e.target.files);
  });

  function handleNewFiles(files) {
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (file.name.endsWith('.xlsx') || file.name.endsWith('.xlsm') || file.name.endsWith('.xls')) {
        selectedFiles.push(file);
      }
    }
    updateFileList();
  }

  function updateFileList() {
    if (selectedFiles.length === 0) {
      fileListContainer.classList.add('hidden');
      return;
    }
    fileListContainer.classList.remove('hidden');
    fileCount.textContent = selectedFiles.length;
    fileList.innerHTML = '';

    selectedFiles.forEach((file, index) => {
      const li = document.createElement('li');
      li.className = 'py-1.5 flex justify-between items-center text-slate-700';
      li.innerHTML = `
        <span class="truncate font-mono">${file.name}</span>
        <span class="text-slate-400 font-sans">${(file.size / 1024).toFixed(1)} KB</span>
      `;
      fileList.appendChild(li);
    });
  }

  clearFilesBtn.addEventListener('click', () => {
    selectedFiles = [];
    fileInput.value = '';
    updateFileList();
  });

  uploadBtn.addEventListener('click', async () => {
    if (selectedFiles.length === 0) return;

    const strategyEl = document.querySelector('input[name="duplicate_strategy"]:checked');
    const duplicateStrategy = strategyEl ? strategyEl.value : 'skip';

    const formData = new FormData();
    formData.append('duplicate_strategy', duplicateStrategy);

    for (let i = 0; i < selectedFiles.length; i++) {
      formData.append('files', selectedFiles[i]);
    }

    uploadBtn.disabled = true;
    fileListContainer.classList.add('hidden');
    uploadProgress.classList.remove('hidden');
    resultsCard.classList.add('hidden');

    try {
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Error en la subida');
      }

      const data = await response.json();
      renderBatchResults(data);
    } catch (err) {
      alert(`Error al procesar lote: ${err.message}`);
    } finally {
      uploadProgress.classList.add('hidden');
      uploadBtn.disabled = false;
      selectedFiles = [];
      fileInput.value = '';
    }
  });

  function renderBatchResults(summary) {
    document.getElementById('res-success-count').textContent = summary.success_count;
    document.getElementById('res-updated-count').textContent = summary.updated_count;
    document.getElementById('res-skipped-count').textContent = summary.skipped_count;
    document.getElementById('res-error-count').textContent = summary.error_count;

    resultsTableBody.innerHTML = '';

    summary.results.forEach(item => {
      const tr = document.createElement('tr');
      
      let badgeHtml = '';
      if (item.status === 'success') {
        badgeHtml = '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">Éxito</span>';
      } else if (item.status === 'updated_duplicate') {
        badgeHtml = '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800">Actualizado</span>';
      } else if (item.status === 'skipped_duplicate') {
        badgeHtml = '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-700">Ignorado</span>';
      } else {
        badgeHtml = '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 text-rose-800">Error</span>';
      }

      tr.innerHTML = `
        <td class="py-2.5 px-3 font-mono font-medium text-slate-800">${item.filename}</td>
        <td class="py-2.5 px-3">${badgeHtml}</td>
        <td class="py-2.5 px-3 font-mono text-sky-700">${item.curp || '-'}</td>
        <td class="py-2.5 px-3">${item.vacuna || '-'}</td>
        <td class="py-2.5 px-3">${item.fecha_aplicacion || '-'}</td>
        <td class="py-2.5 px-3 text-slate-500">${item.message}</td>
      `;
      resultsTableBody.appendChild(tr);
    });

    resultsCard.classList.remove('hidden');
    resultsCard.scrollIntoView({ behavior: 'smooth' });
  }
});
