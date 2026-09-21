// Image compression in browser to prevent mobile RAM crashing
function optimizePhoto(file) {
  return new Promise((resolve) => {
    if (!file || file.size < 400 * 1024) {
      resolve(file);
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        let maxDim = 800, w = img.width, h = img.height;
        if (w > h && w > maxDim) { h = Math.round((h * maxDim) / w); w = maxDim; }
        else if (h > maxDim) { w = Math.round((w * maxDim) / h); h = maxDim; }
        const canvas = document.createElement("canvas");
        canvas.width = w; canvas.height = h;
        canvas.getContext("2d").drawImage(img, 0, 0, w, h);
        canvas.toBlob((b) => resolve(new File([b], "leaf.jpg", { type: "image/jpeg" })), "image/jpeg", 0.85);
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
}

async function handleCapturedImage(file) {
  if (!file) return;

  const preview = document.getElementById("leafPreviewImg") || 
                  document.getElementById("preview") || 
                  document.querySelector("img[alt='']");
  if (preview) {
    preview.src = URL.createObjectURL(file);
    preview.style.display = "block";
  }

  const resultContainer = document.getElementById("result") || document.querySelector(".results-container");
  if (resultContainer) {
    resultContainer.innerHTML = "<p style='color:#2e7d32; font-weight:bold;'>⚡ Analyzing leaf disease...</p>";
  }

  try {
    const readyFile = await optimizePhoto(file);
    const fd = new FormData();
    fd.append("file", readyFile);

    const res = await fetch("/api/predict", { method: "POST", body: fd });
    const data = await res.json();

    if (!data.success) throw new Error(data.error || "Inference failed");

    const cleanName = data.prediction.replace(/___/g, " — ").replace(/_/g, " ");
    let topList = "";
    if (data.top5) {
      topList = "<ul style='margin:6px 0 0 16px; padding:0; font-size:13px; color:#444;'>";
      data.top5.slice(0, 3).forEach(i => {
        topList += `<li>${i.class.replace(/___/g, " — ").replace(/_/g, " ")}: <strong>${i.confidence.toFixed(1)}%</strong></li>`;
      });
      topList += "</ul>";
    }

    if (resultContainer) {
      if (data.isNotPlantLeaf) {
        resultContainer.innerHTML = `
          <div style="background:#fff3e0; padding:12px; border-radius:8px; border-left:4px solid #ff9800;">
            <strong style="color:#e65100;">Notice:</strong>
            <p style="margin:4px 0 0 0; font-size:13px; color:#555;">Please hold the camera 4–6 inches from a single leaf and try again.</p>
          </div>`;
      } else {
        resultContainer.innerHTML = `
          <div style="background:#e8f5e9; padding:14px; border-radius:8px; border-left:4px solid #4caf50;">
            <div style="font-size:16px; font-weight:700; color:#2e7d32;">Diagnosis: ${cleanName}</div>
            <div style="font-size:13px; color:#555; margin-top:3px;">Confidence: <strong>${data.confidence.toFixed(1)}%</strong></div>
            <div style="margin-top:8px;">${topList}</div>
            <div id="aiRemedyArea" style="margin-top:10px; padding-top:8px; border-top:1px dashed #a5d6a7;">
              <span style="font-size:12px; color:#2e7d32;">🌱 Requesting remedy recommendations...</span>
            </div>
          </div>`;

        fetch("/api/remedy", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ diseaseName: cleanName, confidence: data.confidence })
        })
        .then(r => r.json())
        .then(rData => {
          const area = document.getElementById("aiRemedyArea");
          if (area && rData.remedy) {
            area.innerHTML = `<strong>Treatment:</strong><p style="font-size:13px; color:#1b5e20; margin:4px 0 0 0; line-height:1.4;">${rData.remedy}</p>`;
          }
        })
        .catch(() => {});
      }
    }
  } catch (err) {
    if (resultContainer) {
      resultContainer.innerHTML = "<p style='color:red; font-weight:bold;'>Analysis failed. Please try again with clear lighting.</p>";
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  let camInput = document.getElementById("nativeCamInput");
  if (!camInput) {
    camInput = document.createElement("input");
    camInput.type = "file";
    camInput.id = "nativeCamInput";
    camInput.accept = "image/*";
    camInput.setAttribute("capture", "environment");
    camInput.style.display = "none";
    document.body.appendChild(camInput);
  }

  let galInput = document.getElementById("nativeGalInput");
  if (!galInput) {
    galInput = document.createElement("input");
    galInput.type = "file";
    galInput.id = "nativeGalInput";
    galInput.accept = "image/*";
    galInput.style.display = "none";
    document.body.appendChild(galInput);
  }

  camInput.addEventListener("change", (e) => { if (e.target.files[0]) handleCapturedImage(e.target.files[0]); });
  galInput.addEventListener("change", (e) => { if (e.target.files[0]) handleCapturedImage(e.target.files[0]); });

  document.querySelectorAll("button, .btn").forEach((btn) => {
    const txt = (btn.innerText || "").toLowerCase();
    if (txt.includes("open camera") || txt.includes("camera")) {
      btn.onclick = (e) => { e.preventDefault(); camInput.click(); };
    } else if (txt.includes("click image") || txt.includes("choose") || txt.includes("upload") || txt.includes("photo")) {
      btn.onclick = (e) => { e.preventDefault(); galInput.click(); };
    }
  });

  document.querySelectorAll('input[type="file"]').forEach((inp) => {
    inp.addEventListener("change", (e) => { if (e.target.files[0]) handleCapturedImage(e.target.files[0]); });
  });
});
