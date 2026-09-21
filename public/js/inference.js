function prepareMobilePhoto(file, maxDimension = 800) {
  return new Promise((resolve) => {
    if (!file || file.size < 400 * 1024) {
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
            resolve(new File([blob], "leaf.jpg", { type: "image/jpeg" }));
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

async function handleImageUpload(file) {
  if (!file) return;

  const resultBox = document.getElementById("result") || document.querySelector(".results-container");
  const previewBox = document.getElementById("preview") || document.querySelector(".preview-image");

  if (previewBox) {
    previewBox.src = URL.createObjectURL(file);
    previewBox.style.display = "block";
  }

  if (resultBox) {
    resultBox.innerHTML = "<p style='color:#2e7d32; font-weight:bold; font-size:16px;'>⚡ Analyzing leaf condition...</p>";
  }

  try {
    const optimizedFile = await prepareMobilePhoto(file);
    const formData = new FormData();
    formData.append("file", optimizedFile);

    const res = await fetch("/api/predict", {
      method: "POST",
      body: formData
    });

    if (!res.ok) throw new Error("Inference service error");
    const data = await res.json();
    renderPrediction(data);
  } catch (err) {
    console.error("Inference Error:", err);
    if (resultBox) {
      resultBox.innerHTML = "<p style='color:#d32f2f; font-weight:bold;'>Detection failed. Please ensure the leaf is clearly centered and well-lit.</p>";
    }
  }
}

function renderPrediction(data) {
  const resultBox = document.getElementById("result") || document.querySelector(".results-container");
  if (!resultBox) return;

  if (data.isNotPlantLeaf) {
    resultBox.innerHTML = `
      <div style="background:#fff3e0; padding:15px; border-radius:10px; border-left:5px solid #ff9800;">
        <h3 style="color:#e65100; margin:0 0 6px 0;">Leaf Not Detected</h3>
        <p style="margin:0; font-size:14px; color:#555;">Please snap a closer photo focusing on a single leaf (keep camera 4–6 inches away).</p>
      </div>
    `;
    return;
  }

  const cleanName = data.prediction.replace(/___/g, " — ").replace(/_/g, " ");

  let top5Html = "";
  if (data.top5 && data.top5.length > 0) {
    top5Html = "<ul style='padding-left:18px; margin:8px 0 0 0;'>";
    data.top5.slice(0, 3).forEach((item) => {
      const name = item.class.replace(/___/g, " — ").replace(/_/g, " ");
      top5Html += `<li style="font-size:13px; color:#444;">${name}: <strong>${item.confidence}%</strong></li>`;
    });
    top5Html += "</ul>";
  }

  resultBox.innerHTML = `
    <div style="background:#e8f5e9; padding:15px; border-radius:10px; border-left:5px solid #4caf50;">
      <h3 style="color:#2e7d32; margin:0 0 6px 0; font-size:18px;">Diagnosis: ${cleanName}</h3>
      <p style="margin:0; font-size:14px; color:#333;">Confidence: <strong>${data.confidence}%</strong></p>
      <div style="margin-top:8px;">
        <span style="font-size:12px; font-weight:bold; color:#666;">Top Possibilities:</span>
        ${top5Html}
      </div>
    </div>
  `;

  if (typeof fetchRemedy === "function") {
    fetchRemedy(cleanName, data.confidence);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const fileInput = document.getElementById("imageInput") || document.querySelector('input[type="file"]');
  if (fileInput) {
    fileInput.setAttribute("accept", "image/*");
    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        handleImageUpload(e.target.files[0]);
      }
    });
  }
});
