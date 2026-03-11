document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("upload-form");
    const fileInput = document.getElementById("file-input");
    const fileNameEl = document.getElementById("file-name");
    const dropZone = document.getElementById("drop-zone");
    const lazOptions = document.getElementById("laz-options");
    const hillshadeToggle = document.getElementById("enable-hillshade");
    const hillshadeOpts = document.getElementById("hillshade-options");
    const hillshadeToggleGroup = document.getElementById("hillshade-toggle-group");
    const submitBtn = document.getElementById("submit-btn");
    const statusEl = document.getElementById("status");
    const statusText = document.getElementById("status-text");
    const progressFill = document.getElementById("progress-fill");
    const resultsEl = document.getElementById("results");
    const downloadLinks = document.getElementById("download-links");
    const errorBox = document.getElementById("error-box");
    const T = JSON.parse(document.body.dataset.translations);

    // Slider value display
    document.querySelectorAll('input[type="range"]').forEach((slider) => {
        const valSpan = document.getElementById(slider.id + "-val");
        if (valSpan) {
            slider.addEventListener("input", () => {
                valSpan.textContent = slider.value;
            });
        }
    });

    // Hillshade toggle
    hillshadeToggle.addEventListener("change", () => {
        hillshadeOpts.classList.toggle("hidden", !hillshadeToggle.checked);
    });

    // File type detection - show/hide LAZ options
    function updateFormForFile(filename) {
        if (!filename) return;
        const ext = filename.split(".").pop().toLowerCase();
        const isTif = ext === "tif" || ext === "tiff";

        if (isTif) {
            lazOptions.classList.add("hidden");
            hillshadeToggle.checked = true;
            hillshadeOpts.classList.remove("hidden");
            hillshadeToggleGroup.classList.add("hidden");
        } else {
            lazOptions.classList.remove("hidden");
            hillshadeToggleGroup.classList.remove("hidden");
        }
    }

    fileInput.addEventListener("change", () => {
        if (fileInput.files.length) {
            fileNameEl.textContent = fileInput.files[0].name;
            updateFormForFile(fileInput.files[0].name);
        }
    });

    // Drag and drop
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("drag-over");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("drag-over");
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("drag-over");
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            fileNameEl.textContent = e.dataTransfer.files[0].name;
            updateFormForFile(e.dataTransfer.files[0].name);
        }
    });

    // Form submit — uses XMLHttpRequest for upload progress
    form.addEventListener("submit", (e) => {
        e.preventDefault();
        hideAll();

        if (!fileInput.files.length) return;

        // Check file size client-side
        if (fileInput.files[0].size > 540 * 1024 * 1024) {
            showError(T.file_too_large);
            return;
        }

        submitBtn.disabled = true;
        submitBtn.textContent = T.processing;
        statusEl.classList.remove("hidden");
        statusText.textContent = T.status_uploading || "Uploading...";
        progressFill.style.width = "0%";

        const formData = new FormData(form);
        if (!hillshadeToggle.checked) {
            formData.delete("enable_hillshade");
        }

        const xhr = new XMLHttpRequest();

        // Upload progress: 0-50% of progress bar
        xhr.upload.addEventListener("progress", (ev) => {
            if (ev.lengthComputable) {
                const pct = Math.round((ev.loaded / ev.total) * 50);
                progressFill.style.width = pct + "%";
                statusText.textContent = (T.status_uploading || "Uploading...") +
                    " " + Math.round(ev.loaded / 1024 / 1024) + " / " +
                    Math.round(ev.total / 1024 / 1024) + " MB";
            }
        });

        xhr.addEventListener("load", () => {
            try {
                const data = JSON.parse(xhr.responseText);
                if (xhr.status >= 200 && xhr.status < 300) {
                    progressFill.style.width = "50%";
                    pollStatus(data.task_id, data.job_id);
                } else {
                    showError(data.error || T.error);
                    statusEl.classList.add("hidden");
                    resetBtn();
                }
            } catch {
                showError(T.error);
                statusEl.classList.add("hidden");
                resetBtn();
            }
        });

        xhr.addEventListener("error", () => {
            showError(T.error);
            statusEl.classList.add("hidden");
            resetBtn();
        });

        xhr.open("POST", "/upload");
        xhr.send(formData);
    });

    // Processing progress: 50-100% of progress bar
    function pollStatus(taskId, jobId) {
        statusText.textContent = T.status_pending;

        const interval = setInterval(async () => {
            try {
                const resp = await fetch(`/status/${taskId}`);
                const data = await resp.json();

                if (data.state === "pending") {
                    statusText.textContent = T.status_pending;
                    progressFill.style.width = "55%";
                } else if (data.state === "processing") {
                    statusText.textContent = T.status_processing;
                    const steps = { reading: 60, filtering: 70, rasterizing: 80, hillshade: 90 };
                    progressFill.style.width = (steps[data.step] || 65) + "%";
                } else if (data.state === "done") {
                    clearInterval(interval);
                    statusText.textContent = T.status_done;
                    progressFill.style.width = "100%";
                    showResults(jobId, data.files);
                    resetBtn();
                } else if (data.state === "failed") {
                    clearInterval(interval);
                    statusEl.classList.add("hidden");
                    showError(data.error || T.status_failed);
                    resetBtn();
                }
            } catch {
                clearInterval(interval);
                showError(T.error);
                resetBtn();
            }
        }, 2000);
    }

    function showResults(jobId, files) {
        downloadLinks.innerHTML = "";
        if (files.dem) {
            const a = document.createElement("a");
            a.href = `/download/${jobId}/${files.dem}`;
            a.textContent = T.download;
            downloadLinks.appendChild(a);
        }
        if (files.hillshade) {
            const a = document.createElement("a");
            a.href = `/download/${jobId}/${files.hillshade}`;
            a.textContent = T.download_hillshade;
            downloadLinks.appendChild(a);
        }
        resultsEl.classList.remove("hidden");
    }

    function showError(msg) {
        errorBox.textContent = msg;
        errorBox.classList.remove("hidden");
    }

    function hideAll() {
        errorBox.classList.add("hidden");
        resultsEl.classList.add("hidden");
        statusEl.classList.add("hidden");
        progressFill.style.width = "0%";
    }

    function resetBtn() {
        submitBtn.disabled = false;
        submitBtn.textContent = T.submit;
    }
});
