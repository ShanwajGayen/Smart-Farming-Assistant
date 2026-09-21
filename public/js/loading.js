document.addEventListener("DOMContentLoaded", () => {
  const loader = document.getElementById("loading") || document.querySelector(".loading-overlay") || document.querySelector(".loader");
  const video = document.querySelector("#loading video") || document.querySelector("video");

  function hideLoader() {
    if (!loader) return;
    loader.style.transition = "opacity 0.3s ease-out";
    loader.style.opacity = "0";
    setTimeout(() => {
      loader.style.display = "none";
      document.body.style.overflow = "auto";
    }, 300);
  }

  if (video) {
    video.muted = true;
    video.playsInline = true;
    video.setAttribute("playsinline", "");
    video.setAttribute("webkit-playsinline", "");
    video.play().catch(() => hideLoader());
    video.addEventListener("ended", hideLoader);
  }

  if (loader) {
    loader.addEventListener("click", hideLoader);
    loader.addEventListener("touchstart", hideLoader, { passive: true });
  }

  setTimeout(hideLoader, 1200);
});
