// Loaded main app
console.log('App ready');


// --- Mobile Camera & Preview Fix ---
document.addEventListener("DOMContentLoaded", () => {
  // Ensure hidden camera & gallery inputs exist
  let camIn = document.getElementById("nativeCamIn");
  if (!camIn) {
    camIn = document.createElement("input");
    camIn.type = "file";
    camIn.id = "nativeCamIn";
    camIn.accept = "image/*";
    camIn.setAttribute("capture", "environment");
    camIn.style.display = "none";
    document.body.appendChild(camIn);
  }

  let galIn = document.getElementById("nativeGalIn");
  if (!galIn) {
    galIn = document.createElement("input");
    galIn.type = "file";
    galIn.id = "nativeGalIn";
    galIn.accept = "image/*";
    galIn.style.display = "none";
    document.body.appendChild(galIn);
  }

  function handleMobileSelection(file) {
    if (!file) return;
    const preview = document.getElementById("previewImg") || document.querySelector(".preview-image") || document.querySelector("img[alt='']");
    if (preview) {
      preview.src = URL.createObjectURL(file);
      preview.style.display = "block";
    }
    const input = document.getElementById("imageInput") || document.querySelector("input[type='file']");
    if (input) {
      const dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  camIn.addEventListener("change", (e) => { if (e.target.files[0]) handleMobileSelection(e.target.files[0]); });
  galIn.addEventListener("change", (e) => { if (e.target.files[0]) handleMobileSelection(e.target.files[0]); });

  document.querySelectorAll("button, .btn").forEach((b) => {
    const t = (b.innerText || "").toLowerCase();
    if (t.includes("open camera") || t.includes("camera")) {
      b.onclick = (e) => { e.preventDefault(); camIn.click(); };
    } else if (t.includes("click image") || t.includes("choose") || t.includes("photo")) {
      b.onclick = (e) => { e.preventDefault(); galIn.click(); };
    }
  });
});
