// Configuration de l'URL de base de l'API (adaptée selon déploiement)
// Ici on assume la même origine (donc chemins relatifs)
const API_BASE = "";

// Récupération du token API à utiliser pour les requêtes (on peut choisir de le demander à l'utilisateur)
let apiToken = localStorage.getItem("apiToken");
if (!apiToken) {
  apiToken = prompt("Entrez votre token d'API pour accéder à l'interface :");
  localStorage.setItem("apiToken", apiToken);
}

// Langues (français/anglais)
const texts = {
  "fr": {
    title: "Leak Detector – Administration",
    dist_section_title: "Distribuer un fichier",
    file_input_label: "Fichier à distribuer :",
    recipients_label: "Destinataires :",
    dist_button: "Distribuer",
    scan_section_title: "Scanner un fichier suspect",
    scan_file_label: "Fichier à analyser :",
    scan_button: "Analyser",
    past_section_title: "Distributions passées",
    th_id: "ID",
    th_file: "Fichier",
    th_date: "Date",
    th_recipients: "Destinataires",
    th_actions: "Actions",
    dist_success: "Distribution effectuée (ID = {id}).",
    scan_not_found: "Aucune empreinte détectée.",
    scan_found: "Fuite détectée ! Destinataire : {recipient}, Distribution #{id} du {date}.",
    download_all: "Télécharger tout",
    download: "Télécharger"
  },
  "en": {
    title: "Leak Detector – Administration",
    dist_section_title: "Distribute a file",
    file_input_label: "File to distribute:",
    recipients_label: "Recipients:",
    dist_button: "Distribute",
    scan_section_title: "Scan a suspicious file",
    scan_file_label: "File to analyze:",
    scan_button: "Analyze",
    past_section_title: "Past Distributions",
    th_id: "ID",
    th_file: "File",
    th_date: "Date",
    th_recipients: "Recipients",
    th_actions: "Actions",
    dist_success: "Distribution completed (ID = {id}).",
    scan_not_found: "No fingerprint detected.",
    scan_found: "Leak detected! Recipient: {recipient}, Distribution #{id} on {date}.",
    download_all: "Download All",
    download: "Download"
  }
};

// Fonction pour changer la langue de l'interface
function setLanguage(lang) {
  const t = texts[lang];
  document.getElementById("title").innerText = t.title;
  document.getElementById("dist_section_title").innerText = t.dist_section_title;
  document.getElementById("file_input_label").innerText = t.file_input_label;
  document.getElementById("recipients_label").innerText = t.recipients_label;
  document.getElementById("dist_button").innerText = t.dist_button;
  document.getElementById("scan_section_title").innerText = t.scan_section_title;
  document.getElementById("scan_file_label").innerText = t.scan_file_label;
  document.getElementById("scan_button").innerText = t.scan_button;
  document.getElementById("past_section_title").innerText = t.past_section_title;
  document.getElementById("th_id").innerText = t.th_id;
  document.getElementById("th_file").innerText = t.th_file;
  document.getElementById("th_date").innerText = t.th_date;
  document.getElementById("th_recipients").innerText = t.th_recipients;
  document.getElementById("th_actions").innerText = t.th_actions;
  // Mémoriser la langue choisie
  localStorage.setItem("lang", lang);
  // Mettre à jour les messages actuels si déjà affichés (optionnel)
}
  
// Initialiser la langue (par défaut 'fr' ou dernier choix)
setLanguage(localStorage.getItem("lang") || "fr");

// Soumission du formulaire de distribution
document.getElementById("distForm").addEventListener("submit", function(e) {
  e.preventDefault();
  const fileInput = document.getElementById("fileInput");
  const recipientsInput = document.getElementById("recipients");
  if (!fileInput.files.length) return;
  const file = fileInput.files[0];
  const recipients = recipientsInput.value;
  const formData = new FormData();
  formData.append("file", file);
  formData.append("recipients", recipients);
  // Appel API distribute
  fetch(API_BASE + "/api/distribute", {
    method: "POST",
    headers: {
      "Authorization": "Bearer " + apiToken
    },
    body: formData
  })
    .then(response => response.json())
    .then(data => {
      const lang = localStorage.getItem("lang") || "fr";
      if (data.detail && data.distribution_id) {
        document.getElementById("dist_status").innerText = texts[lang].dist_success.replace("{id}", data.distribution_id);
        loadDistributions();  // rafraîchir la liste
      } else if (data.detail) {
        document.getElementById("dist_status").innerText = data.detail;
      } else {
        document.getElementById("dist_status").innerText = "Error: " + JSON.stringify(data);
      }
      // Réinitialiser le formulaire
      document.getElementById("distForm").reset();
    })
    .catch(err => {
      document.getElementById("dist_status").innerText = "Erreur: " + err;
    });
});

// Soumission du formulaire de scan
document.getElementById("scanForm").addEventListener("submit", function(e) {
  e.preventDefault();
  const scanFileInput = document.getElementById("scanFileInput");
  if (!scanFileInput.files.length) return;
  const file = scanFileInput.files[0];
  const formData = new FormData();
  formData.append("file", file);
  fetch(API_BASE + "/api/scan", {
    method: "POST",
    headers: {
      "Authorization": "Bearer " + apiToken
    },
    body: formData
  })
    .then(response => response.json())
    .then(data => {
      const lang = localStorage.getItem("lang") || "fr";
      if (data.status === "found") {
        // Construire le message avec les données
        let msg = texts[lang].scan_found;
        msg = msg.replace("{recipient}", data.recipient)
                 .replace("{id}", data.distribution_id)
                 .replace("{date}", data.date);
        document.getElementById("scan_result").innerText = msg;
      } else {
        document.getElementById("scan_result").innerText = texts[lang].scan_not_found;
      }
      document.getElementById("scanForm").reset();
    })
    .catch(err => {
      document.getElementById("scan_result").innerText = "Erreur: " + err;
    });
});

// Fonction pour charger la liste des distributions et remplir le tableau
function loadDistributions() {
  fetch(API_BASE + "/admin/distributions", {
    headers: {
      "Authorization": "Bearer " + apiToken
    }
  })
    .then(response => response.json())
    .then(list => {
      const tbody = document.querySelector("#distTable tbody");
      tbody.innerHTML = "";
      const lang = localStorage.getItem("lang") || "fr";
      list.forEach(dist => {
        const tr = document.createElement("tr");
        // Colonne ID
        const tdId = document.createElement("td");
        tdId.textContent = dist.id;
        tr.appendChild(tdId);
        // Colonne fichier
        const tdFile = document.createElement("td");
        tdFile.textContent = dist.file_name;
        tr.appendChild(tdFile);
        // Colonne date
        const tdDate = document.createElement("td");
        tdDate.textContent = dist.date;
        tr.appendChild(tdDate);
        // Colonne destinataires
        const tdRec = document.createElement("td");
        tdRec.textContent = dist.recipients.join(", ");
        tr.appendChild(tdRec);
        // Colonne actions (téléchargement)
        const tdActions = document.createElement("td");
        tdActions.className = "actions";
        // Bouton pour télécharger tous les fichiers de la distribution (ZIP)
        const btnAll = document.createElement("button");
        btnAll.textContent = texts[lang].download_all;
        btnAll.onclick = () => {
          downloadZip(dist.id);
        };
        tdActions.appendChild(btnAll);
        // (Optionnel) Si on voulait un bouton par destinataire pour téléchargement individuel:
        // dist.recipients.forEach((rec, index) => {...})
        tr.appendChild(tdActions);
        tbody.appendChild(tr);
      });
    })
    .catch(err => {
      console.error("Erreur chargement distributions:", err);
    });
}

// Fonction pour télécharger le ZIP d'une distribution
function downloadZip(distId) {
  fetch(API_BASE + `/admin/distributions/${distId}/download`, {
    headers: {
      "Authorization": "Bearer " + apiToken
    }
  })
    .then(response => {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.blob();
    })
    .then(blob => {
      // Créer un lien de téléchargement temporaire
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `distribution_${distId}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    })
    .catch(err => {
      alert("Erreur lors du téléchargement: " + err);
    });
}

// Charger la liste initiale des distributions au chargement de la page
loadDistributions();
