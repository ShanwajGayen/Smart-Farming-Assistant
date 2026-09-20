// Compress and downscale massive mobile camera photos in the browser
function compressMobilePhoto(file, maxDimension = 800) {
  return new Promise((resolve) => {
    // If it's already small, don't re-encode
    if (file.size < 500 * 1024) {
      resolve(file);
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        let width = img.width;
        let height = img.height;

        if (width > height && width > maxDimension) {
          height = Math.round((height * maxDimension) / width);
          width = maxDimension;
        } else if (height > maxDimension) {
          width = Math.round((width * maxDimension) / height);
          height = maxDimension;
        }

        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, width, height);

        canvas.toBlob(
          (blob) => {
            resolve(new File([blob], file.name || "leaf.jpg", { type: "image/jpeg" }));
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

// Wrap your upload function:
async function handlePredict(imageFile) {
  try {
    // Compress first to prevent phone memory crash
    const preparedFile = await compressMobilePhoto(imageFile);

    const formData = new FormData();
    formData.append("file", preparedFile);

    const response = await fetch("/api/predict", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    return data;
  } catch (err) {
    console.error("Prediction error:", err);
    alert("Prediction failed. Please try uploading a clearer leaf photo.");
  }
}
