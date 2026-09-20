document.addEventListener("DOMContentLoaded", () => {
  const loader = document.getElementById("loading") || document.querySelector(".loading-overlay") || document.querySelector(".loader");
  const video = document.querySelector("#loading video") || document.querySelector("video");

  function dismissLoader() {
    if (!loader) return;
    loader.style.transition = "opacity 0.4s ease-out";
    loader.style.opacity = "0";
    setTimeout(() => {
      loader.style.display = "none";
      document.body.style.overflow = "auto";
    }, 400);
  }

  if (video) {
    video.muted = true;
    video.playsInline = true;
    video.setAttribute("playsinline", "");
    video.setAttribute("webkit-playsinline", "");
    video.play().catch(() => {
      dismissLoader();
    });
    video.addEventListener("ended", dismissLoader);
  }

  if (loader) {
    loader.addEventListener("click", dismissLoader);
    loader.addEventListener("touchstart", dismissLoader, { passive: true });
  }

  setTimeout(dismissLoader, 1500);
});
