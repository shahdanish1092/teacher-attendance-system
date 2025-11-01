// static/js/camera.js
async function startCameraAndAttach(sessionId, token) {
  const video = document.getElementById("video");
  const statusEl = document.getElementById("status");

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    statusEl.innerText = "Camera not supported in this browser.";
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    video.srcObject = stream;
    video.play();

    const captureBtn = document.getElementById("captureBtn");
    captureBtn.addEventListener("click", async () => {
      // draw current frame to canvas
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL("image/jpeg");

      statusEl.innerText = "Verifying...";

      try {
        const resp = await fetch(`/verify_face/${sessionId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image: dataUrl, token: token })
        });
        const j = await resp.json();
        if (j.success) {
          statusEl.innerText = `Recognized: ${j.student_id}`;
        } else {
          statusEl.innerText = `Not recognized: ${j.message || ""}`;
        }
      } catch (err) {
        statusEl.innerText = "Network error: " + err;
      }
    });

  } catch (err) {
    statusEl.innerText = "Camera permission denied or error: " + err;
  }
}
