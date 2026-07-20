(() => {
  const CIRCUMFERENCE = 2 * Math.PI * 54;

  const els = {
    digits: document.getElementById("digits"),
    statusText: document.getElementById("statusText"),
    speakerLabel: document.getElementById("speakerLabel"),
    speakerName: document.getElementById("speakerName"),
    ringProgress: document.getElementById("ringProgress"),
    clockWrap: document.querySelector(".clock-wrap"),
    presets: document.getElementById("presets"),
    customTime: document.getElementById("customTime"),
    queueForm: document.getElementById("queueForm"),
    queueInput: document.getElementById("queueInput"),
    queueList: document.getElementById("queueList"),
    btnStart: document.getElementById("btnStart"),
    btnPause: document.getElementById("btnPause"),
    btnReset: document.getElementById("btnReset"),
    btnFullscreen: document.getElementById("btnFullscreen"),
    overlay: document.getElementById("timeUpOverlay"),
    overlayName: document.getElementById("overlayName"),
    btnNext: document.getElementById("btnNext"),
    btnDismiss: document.getElementById("btnDismiss"),
    optSound: document.getElementById("optSound"),
    optWarn: document.getElementById("optWarn"),
  };

  const state = {
    duration: 300,
    remaining: 300,
    running: false,
    ended: false,
    warned: false,
    raf: null,
    endAt: 0,
    queue: [],
    currentIndex: -1,
  };

  const STORAGE_KEY = "report-clock-queue-v1";

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  function formatTime(totalSeconds) {
    const s = Math.max(0, Math.ceil(totalSeconds));
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${pad(m)}:${pad(sec)}`;
  }

  function parseTimeInput(raw) {
    const text = String(raw || "").trim();
    if (!text) return null;
    if (/^\d+$/.test(text)) {
      const minutes = Number(text);
      if (minutes <= 0 || minutes > 180) return null;
      return minutes * 60;
    }
    const match = text.match(/^(\d{1,3}):([0-5]?\d)$/);
    if (!match) return null;
    const minutes = Number(match[1]);
    const seconds = Number(match[2]);
    const total = minutes * 60 + seconds;
    if (total <= 0 || total > 180 * 60) return null;
    return total;
  }

  function currentSpeaker() {
    if (state.currentIndex < 0 || state.currentIndex >= state.queue.length) {
      return null;
    }
    return state.queue[state.currentIndex];
  }

  function updateSpeakerUI() {
    const speaker = currentSpeaker();
    if (speaker) {
      els.speakerLabel.textContent = "正在汇报";
      els.speakerName.textContent = speaker;
    } else if (state.queue.length > 0) {
      els.speakerLabel.textContent = "下一位汇报";
      els.speakerName.textContent = state.queue[0];
    } else {
      els.speakerLabel.textContent = "下一位汇报";
      els.speakerName.textContent = "准备开始";
    }
  }

  function setRing(progress) {
    const clamped = Math.min(1, Math.max(0, progress));
    els.ringProgress.style.strokeDasharray = String(CIRCUMFERENCE);
    els.ringProgress.style.strokeDashoffset = String(CIRCUMFERENCE * (1 - clamped));
  }

  function setVisualState() {
    els.clockWrap.classList.toggle("is-running", state.running);
    els.clockWrap.classList.toggle("is-warn", false);
    els.clockWrap.classList.toggle("is-over", false);
    document.body.classList.remove("is-warn", "is-over");

    if (state.ended || state.remaining <= 0) {
      els.clockWrap.classList.add("is-over");
      document.body.classList.add("is-over");
      return;
    }
    if (els.optWarn.checked && state.remaining <= 60) {
      els.clockWrap.classList.add("is-warn");
      document.body.classList.add("is-warn");
    }
  }

  function render() {
    els.digits.textContent = formatTime(state.remaining);
    els.digits.setAttribute("datetime", `PT${Math.ceil(state.remaining)}S`);
    setRing(state.duration > 0 ? state.remaining / state.duration : 0);
    setVisualState();
    updateSpeakerUI();

    if (state.ended) {
      els.statusText.textContent = "时间到";
      els.btnStart.textContent = "再来一轮";
      els.btnPause.disabled = true;
    } else if (state.running) {
      els.statusText.textContent = "进行中";
      els.btnStart.textContent = "继续";
      els.btnPause.disabled = false;
    } else if (state.remaining < state.duration) {
      els.statusText.textContent = "已暂停";
      els.btnStart.textContent = "继续";
      els.btnPause.disabled = true;
    } else {
      els.statusText.textContent = "待命";
      els.btnStart.textContent = "开始";
      els.btnPause.disabled = true;
    }
  }

  function saveQueue() {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          queue: state.queue,
          currentIndex: state.currentIndex,
          duration: state.duration,
        })
      );
    } catch {
      /* ignore */
    }
  }

  function loadQueue() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      if (Array.isArray(data.queue)) state.queue = data.queue.filter(Boolean);
      if (typeof data.currentIndex === "number") {
        state.currentIndex = data.currentIndex;
      }
      if (typeof data.duration === "number" && data.duration > 0) {
        state.duration = data.duration;
        state.remaining = data.duration;
      }
    } catch {
      /* ignore */
    }
  }

  function renderQueue() {
    els.queueList.innerHTML = "";
    state.queue.forEach((name, index) => {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "queue-item" + (index === state.currentIndex ? " is-current" : "");
      btn.innerHTML = `<span class="idx">${index + 1}</span><span>${escapeHtml(name)}</span>`;
      btn.addEventListener("click", () => selectSpeaker(index));

      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "remove";
      remove.setAttribute("aria-label", `移除 ${name}`);
      remove.textContent = "×";
      remove.addEventListener("click", (e) => {
        e.stopPropagation();
        removeSpeaker(index);
      });

      btn.appendChild(remove);
      li.appendChild(btn);
      els.queueList.appendChild(li);
    });
  }

  function escapeHtml(text) {
    return String(text)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function selectSpeaker(index) {
    state.currentIndex = index;
    resetTimer(false);
    saveQueue();
    renderQueue();
    render();
  }

  function removeSpeaker(index) {
    state.queue.splice(index, 1);
    if (state.queue.length === 0) {
      state.currentIndex = -1;
    } else if (state.currentIndex >= state.queue.length) {
      state.currentIndex = state.queue.length - 1;
    } else if (index < state.currentIndex) {
      state.currentIndex -= 1;
    }
    saveQueue();
    renderQueue();
    render();
  }

  function ensureSpeakerSelected() {
    if (state.queue.length === 0) return;
    if (state.currentIndex < 0 || state.currentIndex >= state.queue.length) {
      state.currentIndex = 0;
    }
  }

  function playBeep(kind = "end") {
    if (!els.optSound.checked) return;
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const now = ctx.currentTime;
      const notes = kind === "warn" ? [660, 660] : [523.25, 659.25, 783.99];
      notes.forEach((freq, i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0.0001, now + i * 0.18);
        gain.gain.exponentialRampToValueAtTime(0.18, now + i * 0.18 + 0.03);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.18 + 0.28);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now + i * 0.18);
        osc.stop(now + i * 0.18 + 0.32);
      });
      setTimeout(() => ctx.close(), 1200);
    } catch {
      /* ignore */
    }
  }

  function showOverlay() {
    const speaker = currentSpeaker();
    els.overlayName.textContent = speaker || "本轮汇报";
    els.overlay.hidden = false;
    playBeep("end");
  }

  function hideOverlay() {
    els.overlay.hidden = true;
  }

  function tick(now) {
    if (!state.running) return;
    const left = Math.max(0, (state.endAt - now) / 1000);
    state.remaining = left;

    if (els.optWarn.checked && !state.warned && left <= 60 && left > 0) {
      state.warned = true;
      playBeep("warn");
    }

    if (left <= 0) {
      state.remaining = 0;
      state.running = false;
      state.ended = true;
      state.raf = null;
      render();
      showOverlay();
      return;
    }

    render();
    state.raf = requestAnimationFrame(tick);
  }

  function startTimer() {
    if (state.ended) {
      resetTimer(false);
    }
    ensureSpeakerSelected();
    if (state.remaining <= 0) {
      state.remaining = state.duration;
    }
    state.running = true;
    state.ended = false;
    state.endAt = performance.now() + state.remaining * 1000;
    hideOverlay();
    saveQueue();
    renderQueue();
    render();
    if (state.raf) cancelAnimationFrame(state.raf);
    state.raf = requestAnimationFrame(tick);
  }

  function pauseTimer() {
    if (!state.running) return;
    state.running = false;
    if (state.raf) {
      cancelAnimationFrame(state.raf);
      state.raf = null;
    }
    state.remaining = Math.max(0, (state.endAt - performance.now()) / 1000);
    render();
  }

  function resetTimer(clearEndedOverlay = true) {
    state.running = false;
    state.ended = false;
    state.warned = false;
    state.remaining = state.duration;
    if (state.raf) {
      cancelAnimationFrame(state.raf);
      state.raf = null;
    }
    if (clearEndedOverlay) hideOverlay();
    render();
  }

  function setDuration(seconds, syncCustom = true) {
    state.duration = seconds;
    state.remaining = seconds;
    state.ended = false;
    state.warned = false;
    if (state.running) {
      state.endAt = performance.now() + seconds * 1000;
    }
    [...els.presets.querySelectorAll(".chip")].forEach((chip) => {
      chip.classList.toggle("is-active", Number(chip.dataset.seconds) === seconds);
    });
    if (syncCustom) {
      const m = Math.floor(seconds / 60);
      const s = seconds % 60;
      els.customTime.value = s === 0 ? String(m) : `${m}:${pad(s)}`;
    }
    saveQueue();
    render();
  }

  function goNext() {
    hideOverlay();
    if (state.queue.length === 0) {
      resetTimer(false);
      return;
    }
    ensureSpeakerSelected();
    const next = state.currentIndex + 1;
    if (next >= state.queue.length) {
      state.currentIndex = 0;
      els.statusText.textContent = "队列已轮完，从头开始";
    } else {
      state.currentIndex = next;
    }
    resetTimer(false);
    saveQueue();
    renderQueue();
    render();
  }

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen?.().catch(() => {});
    } else {
      document.exitFullscreen?.().catch(() => {});
    }
  }

  els.btnStart.addEventListener("click", startTimer);
  els.btnPause.addEventListener("click", pauseTimer);
  els.btnReset.addEventListener("click", () => resetTimer(true));
  els.btnFullscreen.addEventListener("click", toggleFullscreen);
  els.btnNext.addEventListener("click", goNext);
  els.btnDismiss.addEventListener("click", hideOverlay);

  els.presets.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    const seconds = Number(chip.dataset.seconds);
    if (!seconds) return;
    if (state.running) pauseTimer();
    setDuration(seconds);
  });

  els.customTime.addEventListener("change", () => {
    const seconds = parseTimeInput(els.customTime.value);
    if (!seconds) {
      els.customTime.value = formatTime(state.duration).replace(/^0/, "") || "5:00";
      return;
    }
    if (state.running) pauseTimer();
    setDuration(seconds, false);
  });

  els.queueForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const name = els.queueInput.value.trim();
    if (!name) return;
    state.queue.push(name);
    if (state.currentIndex < 0) state.currentIndex = 0;
    els.queueInput.value = "";
    saveQueue();
    renderQueue();
    render();
  });

  els.optWarn.addEventListener("change", render);

  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, textarea")) return;
    if (e.code === "Space") {
      e.preventDefault();
      if (state.running) pauseTimer();
      else startTimer();
    } else if (e.key === "Escape") {
      hideOverlay();
    } else if (e.key === "n" || e.key === "N") {
      goNext();
    } else if (e.key === "r" || e.key === "R") {
      resetTimer(true);
    } else if (e.key === "f" || e.key === "F") {
      toggleFullscreen();
    }
  });

  // Init
  els.ringProgress.style.strokeDasharray = String(CIRCUMFERENCE);
  loadQueue();
  setDuration(state.duration);
  renderQueue();
  render();
})();
