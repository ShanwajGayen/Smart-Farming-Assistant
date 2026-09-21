// Client-side image compression: prevents mobile browser crash & memory limits
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
            resolve(new File([blob], "crop_leaf.jpg", { type: "image/jpeg" }));
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

// Master handler triggered as soon as a photo is taken or chosen
async function handleFileSelected(file) {
  if (!file) return;

  // Find all possible preview & result elements in DOM
  const previewImg = document.getElementById("preview") || 
                     document.getElementById("previewImg") || 
                     document.getElementById("imagePreview") || 
                     document.querySelector("img[alt*='Preview']") || 
                     document.querySelector(".preview-image");
                     
  const resultBox = document.getElementById("result") || 
                    document.getElementById("predictionResult") || 
                    document.querySelector(".results-container");

  // 1. Immediately display the local image and hide broken placeholder icon
  if (previewImg) {
    previewImg.src = URL.createObjectURL(file);
    previewImg.style.display = "block";
    previewImg.style.maxWidth = "100%";
    previewImg.style.maxHeight = "320px";
    previewImg.style.borderRadius = "12px";
    previewImg.style.objectFit = "contain";
    previewImg.style.margin = "10px auto";
    previewImg.removeAttribute("alt"); // Prevents broken text showing
  }

  // 2. Show analysis progress indicator
  if (resultBox) {
    resultBox.innerHTML = `
      <div style="text-align:center; padding:15px;">
        <p style="color:#2e7d32; font-weight:bold; font-size:16px; margin:0;">
          ⚡ Analyzing leaf disease...
        </p>
      </div>
    `;
  }

  // 3. Compress and send to server
  try {
    const optimizedFile = await compressImage(file);
    const formData = new FormData();
    formData.append("file", optimizedFile);

    const response = await fetch("/api/predict", {
      method: "POST",
      body: formData
    });

    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    const data = await response.json();
    renderResults(data);
  } catch (err) {
    console.error("Prediction error:", err);
    if (resultBox) {
      resultBox.innerHTML = `
        <div style="background:#ffebee; padding:15px; border-radius:8px; border-left:5px solid #d32f2f;">
          <p style="color:#c62828; margin:0; font-weight:bold;">
            Analysis failed. Please snap a closer, well-lit photo of the leaf.
          </p>
        </div>
      `;
    }
  }
}

// Render diagnosis and request AI remedy
function renderResults(data) {
  const resultBox = document.getElementById("result") || 
                    document.getElementById("predictionResult") || 
                    document.querySelector(".results-container");
  if (!resultBox) return;

  if (data.isNotPlantLeaf) {
    resultBox.innerHTML = `
      <div style="background:#fff3e0; padding:15px; border-radius:10px; border-left:5px solid #ff9800;">
        <h3 style="color:#e65100; margin:0 0 6px 0;">Leaf Not Detected</h3>
        <p style="margin:0; font-size:14px; color:#555;">Please hold the camera closer (4–6 inches from the leaf) and try again.</p>
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
    <div style="background:#e8f5e9; padding:16px; border-radius:10px; border-left:5px solid #4caf50;">
      <h3 style="color:#2e7d32; margin:0 0 6px 0; font-size:18px;">Diagnosis: ${cleanName}</h3>
      <p style="margin:0; font-size:14px; color:#333;">Confidence: <strong>${data.confidence}%</strong></p>
      <div style="margin-top:8px;">
        <span style="font-size:12px; font-weight:bold; color:#666;">Top Possibilities:</span>
        ${top5Html}
      </div>
      <div id="remedySection" style="margin-top:12px; padding-top:10px; border-top:1px dashed #a5d6a7;">
        <p style="color:#388e3c; font-size:13px; margin:0;">🌱 Generating treatment recommendations...</p>
      </div>
    </div>
  `;

  // Fetch Remedy from Gemini via /api/remedy
  fetch("/api/remedy", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: json.dumps ? JSON.stringify({ diseaseName: cleanName, language: "en" }) : JSON.stringify({ diseaseName: cleanName })
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

// 5. Connect all UI buttons reliably to phone camera & photo picker
document.addEventListener("DOMContentLoaded", () => {
  // Create or retrieve hidden inputs for Camera and Gallery
  let cameraInput = document.getElementById("cameraInputHidden");
  if (!cameraInput) {
    cameraInput = document.createElement("input");
    cameraInput.type = "file";
    cameraInput.id = "cameraInputHidden";
    cameraInput.accept = "image/*";
    cameraInput.setAttribute("capture", "environment"); // Launches phone rear camera
    cameraInput.style.display = "none";
    document.body.appendChild(cameraInput);
  }

  let galleryInput = document.getElementById("galleryInputHidden");
  if (!galleryInput) {
    galleryInput = document.createElement("input");
    galleryInput.type = "file";
    galleryInput.id = "galleryInputHidden";
    galleryInput.accept = "image/*"; // Launches photo gallery
    galleryInput.style.display = "none";
    document.body.appendChild(galleryInput);
  }

  // Bind change events
  cameraInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) handleFileSelected(e.target.files[0]);
  });
  galleryInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) handleFileSelected(e.target.files[0]);
  });

  // Find all buttons on screen and wire them up
  document.querySelectorAll("button, .btn").forEach((btn) => {
    const text = btn.innerText.toLowerCase();
    if (text.includes("open camera") || text.includes("camera")) {
      btn.onclick = (e) => {
        e.preventDefault();
        cameraInput.click();
      };
    } else if (text.includes("click image") || text.includes("choose") || text.includes("upload") || text.includes("photo")) {
      btn.onclick = (e) => {
        e.preventDefault();
        galleryInput.click();
      };
    }
  });

  // Also bind any visible file inputs
  document.querySelectorAll('input[type="file"]').forEach((input) => {
    input.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) handleFileSelected(e.target.files[0]);
    });
  });
});
