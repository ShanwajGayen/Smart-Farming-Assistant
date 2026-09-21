document.addEventListener("DOMContentLoaded", () => {
  const cameraInput = document.getElementById("cameraInput");
  const galleryInput = document.getElementById("galleryInput");
  const btnCamera = document.getElementById("btnCamera");
  const btnGallery = document.getElementById("btnGallery");
  const previewCard = document.getElementById("previewCard");
  const photoPreview = document.getElementById("photoPreview");
  const resultOutput = document.getElementById("resultOutput");

  if (btnCamera) btnCamera.onclick = () => cameraInput.click();
  if (btnGallery) btnGallery.onclick = () => galleryInput.click();

  if (cameraInput) cameraInput.addEventListener("change", (e) => onFileSelected(e.target.files[0]));
  if (galleryInput) galleryInput.addEventListener("change", (e) => onFileSelected(e.target.files[0]));

  async function onFileSelected(file) {
    if (!file) return;

    // 1. Immediately show live preview on phone screen
    if (previewCard && photoPreview) {
      photoPreview.src = URL.createObjectURL(file);
      previewCard.style.display = "block";
    }

    if (resultOutput) {
      resultOutput.innerHTML = `
        <div style="background:#e8f5e9; border:1px solid #c8e6c9; border-radius:12px; padding:14px; text-align:center;">
          <p style="color:#2e7d32; font-weight:700; margin:0; font-size:15px;">
            ⚡ পাতা বিশ্লেষণ করা হচ্ছে, অনুগ্রহ করে অপেক্ষা করুন...
          </p>
        </div>
      `;
    }

    // 2. Client-side canvas compression (prevents Android browser tab crash)
    const compressed = await new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (evt) => {
        const img = new Image();
        img.onload = () => {
          const maxDim = 800;
          let w = img.width, h = img.height;
          if (w > h && w > maxDim) { h = Math.round((h * maxDim) / w); w = maxDim; }
          else if (h > maxDim) { w = Math.round((w * maxDim) / h); h = maxDim; }
          const canvas = document.createElement("canvas");
          canvas.width = w; canvas.height = h;
          canvas.getContext("2d").drawImage(img, 0, 0, w, h);
          canvas.toBlob((b) => resolve(new File([b], "leaf.jpg", { type: "image/jpeg" })), "image/jpeg", 0.85);
        };
        img.src = evt.target.result;
      };
      reader.readAsDataURL(file);
    });

    // 3. Post to /api/predict
    const fd = new FormData();
    fd.append("file", compressed);

    try {
      const res = await fetch("/api/predict", { method: "POST", body: fd });
      const data = await res.json();

      if (!data.success) throw new Error(data.error || "Inference failed");

      if (data.isNotPlantLeaf) {
        resultOutput.innerHTML = `
          <div style="background:#fff3e0; border-left:5px solid #ff9800; border-radius:12px; padding:14px;">
            <h4 style="color:#e65100; margin:0 0 6px 0; font-size:16px;">⚠️ পাতা শনাক্ত করা যায়নি</h4>
            <p style="color:#666; margin:0; font-size:13px; line-height:1.4;">
              দয়া করে ক্যামেরায় কোনো একটি নির্দিষ্ট পাতার খুব কাছ থেকে (৪-৬ ইঞ্চি দূর থেকে) পরিষ্কার আলোয় ছবি তুলুন।
            </p>
          </div>
        `;
        return;
      }

      let topList = "<ul style='margin:6px 0 0 16px; padding:0; font-size:13px; color:#444;'>";
      if (data.top5) {
        data.top5.slice(0, 3).forEach(i => {
          topList += `<li style="margin-bottom:2px;">${i.class_bn}: <strong>${i.confidence}%</strong></li>`;
        });
      }
      topList += "</ul>";

      resultOutput.innerHTML = `
        <div style="background:#e8f5e9; border-left:5px solid #2e7d32; border-radius:12px; padding:16px; box-shadow:0 3px 10px rgba(0,0,0,0.04);">
          <div style="font-size:13px; color:#666; font-weight:600;">রোগ শনাক্তকরণ ফলাফল:</div>
          <div style="font-size:18px; font-weight:800; color:#1b5e20; margin:4px 0;">${data.prediction_bn}</div>
          <div style="font-size:12px; color:#777; margin-bottom:6px;">(${data.prediction_en})</div>
          <div style="font-size:13px; color:#2e7d32; font-weight:700;">নিশ্চয়তা: ${data.confidence}%</div>
          <div style="margin-top:10px;">
            <span style="font-size:12px; font-weight:700; color:#555;">সম্ভাব্য ফলাফল:</span>
            ${topList}
          </div>
          <div id="bengaliRemedyBox" style="margin-top:14px; padding-top:12px; border-top:1px dashed #a5d6a7;">
            <p style="color:#2e7d32; font-size:13px; font-weight:700; margin:0;">🌱 বিশেষজ্ঞ প্রতিকার তৈরি করা হচ্ছে...</p>
          </div>
        </div>
      `;

      // Request Bengali Remedy from Gemini
      fetch("/api/remedy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ diseaseName: data.prediction_en, confidence: data.confidence, language: "bn" })
      })
      .then(r => r.json())
      .then(rData => {
        const box = document.getElementById("bengaliRemedyBox");
        if (box && rData.remedy) {
          box.innerHTML = `
            <div style="font-size:14px; font-weight:800; color:#1b5e20; margin-bottom:4px;">কৃষি বিশেষজ্ঞের পরামর্শ ও প্রতিকার:</div>
            <div style="font-size:13px; color:#2e7d32; line-height:1.5; white-space:pre-line;">${rData.remedy}</div>
          `;
        }
      })
      .catch(() => {});

    } catch (err) {
      console.error(err);
      if (resultOutput) {
        resultOutput.innerHTML = `
          <div style="background:#ffebee; border-left:5px solid #d32f2f; border-radius:12px; padding:14px;">
            <p style="color:#c62828; font-weight:700; margin:0; font-size:14px;">
              ছবি বিশ্লেষণ করা সম্ভব হয়নি। পাতার পরিষ্কার আলোয় পুনরায় চেষ্টা করুন।
            </p>
          </div>
        `;
      }
    }
  }
});
