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

  // Force video settings for mobile browsers
  if (video) {
    video.muted = true;
    video.playsInline = true;
    video.setAttribute("playsinline", "");
    video.setAttribute("webkit-playsinline", "");
    video.play().catch(() => {
      // Autoplay blocked on mobile - dismiss immediately
      dismissLoader();
    });
    video.addEventListener("ended", dismissLoader);
  }

  // Allow user to tap the screen to skip loading immediately
  if (loader) {
    loader.addEventListener("click", dismissLoader);
    loader.addEventListener("touchstart", dismissLoader, { passive: true });
  }

  // HARD TIMEOUT: Guarantee the loader vanishes after 1.5 seconds on all phones
  setTimeout(dismissLoader, 1500);
});
