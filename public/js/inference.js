// Compress large mobile photos in-browser before upload (Prevents RAM crashes)
function compressImage(file, maxDimension = 800) {
  return new Promise((resolve) => {
    if (!file || file.size < 300 * 1024) {
      resolve(file);
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        let w = img.width;
        let h = img.height;
        if (w > h && w > maxDimension) {
          h = Math.round((h * maxDimension) / w);
          w = maxDimension;
        } else if (h > maxDimension) {
          w = Math.round((w * maxDimension) / h);
          h = maxDimension;
        }
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, w, h);
        canvas.toBlob(
          (blob) => {
            resolve(new File([blob], "crop.jpg", { type: "image/jpeg" }));
          },
          "image/jpeg",
          0.85
        );
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
}

// Master handler when user captures or picks an image
async function onFileSelected(file) {
  if (!file) return;

  const preview = document.getElementById("previewImg");
  const previewLabel = document.getElementById("previewLabel");
  const resultBox = document.getElementById("resultBox");

  // Show local preview immediately
  if (preview) {
    preview.src = URL.createObjectURL(file);
    preview.style.display = "block";
  }
  if (previewLabel) {
    previewLabel.style.display = "block";
  }

  // Show processing status
  if (resultBox) {
    resultBox.innerHTML = `
      <div style="background:#e8f5e9; padding:12px; border-radius:8px; text-align:center;">
        <p style="color:#2e7d32; font-weight:bold; margin:0;">⚡ Diagnosing crop leaf...</p>
      </div>
    `;
  }

  try {
    const preparedFile = await compressImage(file);
    const formData = new FormData();
    formData.append("file", preparedFile);

    const response = await fetch("/api/predict", {
      method: "POST",
      body: formData
    });

    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    const data = await response.json();
    displayDiagnosis(data);
  } catch (err) {
    console.error("Prediction error:", err);
    if (resultBox) {
      resultBox.innerHTML = `
        <div style="background:#ffebee; padding:12px; border-radius:8px; border-left:4px solid #d32f2f;">
          <p style="color:#c62828; margin:0; font-weight:bold;">Diagnosis failed. Please ensure the leaf is clearly centered and well-lit.</p>
        </div>
      `;
    }
  }
}

// Render diagnosis and request AI remedies
function displayDiagnosis(data) {
  const resultBox = document.getElementById("resultBox");
  if (!resultBox) return;

  if (data.isNotPlantLeaf) {
    resultBox.innerHTML = `
      <div style="background:#fff3e0; padding:14px; border-radius:10px; border-left:5px solid #ff9800;">
        <h3 style="color:#e65100; margin:0 0 4px 0; font-size:16px;">Leaf Not Detected</h3>
        <p style="margin:0; font-size:14px; color:#555;">Please hold the camera closer (4–6 inches from the leaf) and try again.</p>
      </div>
    `;
    return;
  }

  const cleanName = data.prediction.replace(/___/g, " — ").replace(/_/g, " ");

  let top5Html = "";
  if (data.top5 && data.top5.length > 0) {
    top5Html = "<ul style='padding-left:18px; margin:6px 0 0 0;'>";
    data.top5.slice(0, 3).forEach((item) => {
      const name = item.class.replace(/___/g, " — ").replace(/_/g, " ");
      top5Html += `<li style="font-size:13px; color:#444;">${name}: <strong>${item.confidence}%</strong></li>`;
    });
    top5Html += "</ul>";
  }

  resultBox.innerHTML = `
    <div style="background:#e8f5e9; padding:15px; border-radius:10px; border-left:5px solid #4caf50;">
      <h3 style="color:#2e7d32; margin:0 0 4px 0; font-size:18px;">Diagnosis: ${cleanName}</h3>
      <p style="margin:0; font-size:14px; color:#333;">Confidence: <strong>${data.confidence}%</strong></p>
      <div style="margin-top:8px;">
        <span style="font-size:12px; font-weight:bold; color:#666;">Top Match:</span>
        ${top5Html}
      </div>
      <div id="remedySection" style="margin-top:12px; padding-top:8px; border-top:1px dashed #a5d6a7;">
        <p style="color:#388e3c; font-size:13px; margin:0;">🌱 Loading treatment remedy...</p>
      </div>
    </div>
  `;

  // Fetch Remedy from Gemini via /api/remedy
  fetch("/api/remedy", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ diseaseName: cleanName, language: "en" })
  })
  .then(res => res.json())
  .then(resData => {
    const remedyDiv = document.getElementById("remedySection");
    if (remedyDiv && resData.remedy) {
      remedyDiv.innerHTML = `
        <h4 style="color:#1b5e20; margin:4px 0;">Recommended Treatment:</h4>
        <p style="font-size:14px; color:#2e7d32; line-height:1.4; margin:4px 0 0 0;">${resData.remedy}</p>
      `;
    }
  })
  .catch(e => console.error(e));
}

// Connect file inputs
document.addEventListener("DOMContentLoaded", () => {
  const cameraIn = document.getElementById("cameraInput");
  const galleryIn = document.getElementById("galleryInput");

  if (cameraIn) {
    cameraIn.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) onFileSelected(e.target.files[0]);
    });
  }
  if (galleryIn) {
    galleryIn.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) onFileSelected(e.target.files[0]);
    });
  }
});
