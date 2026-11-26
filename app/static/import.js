const app = document.getElementById("import-app");
const input = document.getElementById("file-input");
const dropZone = document.getElementById("drop-zone");
const progress = document.getElementById("progress");
const statusText = document.getElementById("status");
const errorsList = document.getElementById("errors");
const previewSection = document.getElementById("preview-section");
const previewSummary = document.getElementById("preview-summary");
const previewBody = document.getElementById("preview-body");
const confirmButton = document.getElementById("confirm-button");
const cancelButton = document.getElementById("cancel-button");

const maxBytes = Number(app.dataset.maxBytes);

let uploadId = null;
let busy = false;
let confirmationUncertain = false;

function showErrors(errors) {
  errorsList.replaceChildren();

  for (const error of errors) {
    const item = document.createElement("li");
    const line = error.source_line
      ? `Ligne ${error.source_line} — `
      : "";
    const field = error.field ? `${error.field} — ` : "";

    item.textContent =
      `${line}${field}${error.code} : ${error.message}`;

    errorsList.appendChild(item);
  }
}

function updateControls() {
  input.disabled = busy || uploadId !== null;
  confirmButton.disabled = busy || uploadId === null;
  cancelButton.disabled =
    busy || uploadId === null || confirmationUncertain;
}

function showPreview(result) {
  const preview = result.preview;
  previewBody.replaceChildren();

  function cell(value) {
    const td = document.createElement("td");
    td.textContent = value == null ? "—" : String(value);
    return td;
  }

  const colors = {
    DEBUG: "#718096",
    INFO: "#1268ed",
    WARNING: "#a97400",
    ERROR: "#c52e42",
    CRITICAL: "#781b27",
  };

  for (const row of preview.events) {
    const tr = document.createElement("tr");
    const event = row.event || {};
    const invalid = row.errors.length > 0;

    if (invalid) tr.classList.add("invalid-row");

    const levelCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = "level-badge";
    badge.textContent = event.level || "—";
    badge.style.color = colors[event.level] || "#5d6d82";
    levelCell.append(badge);

    const messageCell = cell(
      row.event === null ? "Ligne non décodable" : event.message
    );
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    const code = document.createElement("pre");

    summary.textContent = "Voir le document";
    code.textContent = JSON.stringify(row.event, null, 2);
    details.append(summary, code);
    messageCell.append(details);

    const check = cell(invalid ? "Invalide" : "Valide dans l’aperçu");
    check.className = invalid ? "check-invalid" : "check-valid";

    tr.append(
      cell(row.source_line),
      cell(event.timestamp),
      levelCell,
      cell(event.service),
      messageCell,
      cell(event.event_type),
      check
    );
    previewBody.append(tr);
  }

  previewSummary.textContent =
    `${result.original_filename} — ` +
    `${preview.preview_count} événement(s) prévisualisé(s).`;

  previewSection.hidden = false;
  showErrors(preview.errors);
}

function uploadFile(file) {
  if (busy || uploadId !== null) {
    statusText.textContent =
      "Confirmez ou annulez le dépôt actuel avant d’en choisir un autre.";
    return;
  }

  window.dispatchEvent(new CustomEvent("import-file-selected", {
    detail: { name: file.name, size: file.size },
  }));

  showErrors([]);
  previewSection.hidden = true;
  progress.hidden = true;

  if (!/\.(csv|json|jsonl|txt)$/i.test(file.name)) {
    statusText.textContent = "Extension de fichier non autorisée.";
    return;
  }

  if (file.size > maxBytes) {
    statusText.textContent = "Le fichier dépasse la taille autorisée.";
    return;
  }

  busy = true;
  confirmationUncertain = false;
  updateControls();

  progress.value = 0;
  progress.hidden = false;
  statusText.textContent = "Envoi du fichier…";

  const form = new FormData();
  form.append("file", file);

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/imports/preview");

  xhr.upload.onprogress = (event) => {
    if (event.lengthComputable) {
      const percent = Math.round(event.loaded / event.total * 100);
      progress.value = percent;
      statusText.textContent = percent === 100
        ? "Envoi terminé ; vérification du fichier…"
        : `Envoi du fichier : ${percent} %`;
    }
  };

  xhr.onload = () => {
    try {
      const result = JSON.parse(xhr.responseText);

      if (result.preview) {
        showPreview(result);
      }

      if (xhr.status === 201 && result.preview.can_confirm) {
        uploadId = result.upload_id;
        statusText.textContent =
          "Aperçu conforme. Vous pouvez confirmer ou annuler.";
      } else {
        statusText.textContent =
          "Dépôt refusé. Corrigez le fichier puis déposez-le à nouveau.";

        if (result.error) {
          showErrors([result.error]);
        }
      }
    } catch {
      statusText.textContent = "Réponse du serveur illisible.";
    }
  };

  xhr.onerror = () => {
    statusText.textContent =
      "Connexion interrompue ; le résultat du dépôt n’a pas pu être reçu.";
  };

  xhr.onloadend = () => {
    busy = false;
    input.value = "";
    updateControls();
  };

  xhr.send(form);
}

async function applyAction(action) {
  if (busy || uploadId === null) return;

  busy = true;
  showErrors([]);
  statusText.textContent = action === "confirm"
    ? "Confirmation en cours…"
    : "Annulation en cours…";
  updateControls();

  try {
    const response = await fetch(
      `/api/imports/${uploadId}/${action}`,
      { method: "POST" }
    );

    const result = await response.json();

    if (!response.ok) {
      if (action === "confirm" && response.status >= 500) {
        confirmationUncertain = true;
      }
      showErrors(result.error ? [result.error] : result.preview?.errors || []);
      statusText.textContent =
        result.message || result.error?.message || "Action impossible.";
      return;
    }

    uploadId = null;
    confirmationUncertain = false;

    if (action === "confirm") {
      statusText.textContent =
        "Import enregistré. Le suivi est affiché ci-dessous.";

      window.dispatchEvent(new CustomEvent("import-confirmed", {
        detail: { uploadId: result.upload_id },
      }));
    } else {
      statusText.textContent =
        "Dépôt annulé ; aucune ingestion déclenchée.";
      previewSection.hidden = true;
    }
  } catch {
    if (action === "confirm") confirmationUncertain = true;

    statusText.textContent = action === "confirm"
      ? "Résultat non reçu. Réessayez la confirmation du même dépôt."
      : "Résultat non reçu. Réessayez l’annulation.";
  } finally {
    busy = false;
    updateControls();
  }
}

input.addEventListener("change", () => {
  if (input.files.length === 1) uploadFile(input.files[0]);
});

for (const name of ["dragenter", "dragover"]) {
  dropZone.addEventListener(name, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragover");
  });
}

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("dragover");

  if (event.dataTransfer.files.length !== 1) {
    statusText.textContent = "Déposez un seul fichier à la fois.";
    return;
  }

  uploadFile(event.dataTransfer.files[0]);
});

confirmButton.addEventListener("click", () => applyAction("confirm"));
cancelButton.addEventListener("click", () => applyAction("cancel"));