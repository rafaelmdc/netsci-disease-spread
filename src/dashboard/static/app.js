// Live outbreak console: stream a run day-by-day over SSE and draw the epidemic
// curve as it builds. The chart is the hero — it is literally the simulation.

const COMP = {
  S: { name: "Susceptible", color: "#3ba7c4" },
  E: { name: "Exposed",     color: "#f2c14e" },
  I: { name: "Infectious",  color: "#ff6b5e" },
  Q: { name: "Quarantined", color: "#f2c14e" },
  R: { name: "Recovered",   color: "#5fd08a" },
  V: { name: "Vaccinated",  color: "#b98cff" },
};

function fmt(n) {
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return Math.round(n).toString();
}

function startMonitor(jobId) {
  const chart = document.getElementById("live-chart");
  const dayEl = document.getElementById("day-now");
  const ofEl = document.getElementById("day-of");
  const bar = document.getElementById("bar-fill");
  const statsEl = document.getElementById("live-stats");
  const statusEl = document.getElementById("live-status");

  let horizon = 1, fromDay = 0, order = [], idx = {};

  function setStatus(text, cls) {
    statusEl.textContent = text;
    statusEl.className = "badge " + cls;
  }

  function initChart(comps) {
    order = comps;
    const traces = comps.map((c, i) => {
      idx[c] = i;
      const meta = COMP[c] || { name: c, color: "#8a97b2" };
      return { x: [], y: [], mode: "lines", name: meta.name,
               line: { color: meta.color, width: 2.5 } };
    });
    const layout = {
      paper_bgcolor: "transparent", plot_bgcolor: "transparent",
      font: { color: "#8a97b2", family: "IBM Plex Mono, monospace", size: 11 },
      margin: { l: 56, r: 16, t: 10, b: 38 },
      xaxis: { title: "day", gridcolor: "#1e2742", zeroline: false },
      yaxis: { title: "people", gridcolor: "#1e2742", zeroline: false },
      legend: { orientation: "h", y: -0.22 },
      showlegend: true,
    };
    Plotly.newPlot(chart, traces, layout, { displaylogo: false, responsive: true });
  }

  function pushDay(day, totals) {
    const xs = order.map(() => [day]);
    const ys = order.map((c) => [totals[c] ?? 0]);
    Plotly.extendTraces(chart, { x: xs, y: ys }, order.map((_, i) => i));
    dayEl.textContent = day + 1;
    bar.style.width = Math.min(100, ((day + 1) / horizon) * 100) + "%";
    statsEl.innerHTML = order.map((c) => {
      const meta = COMP[c] || { name: c, color: "#8a97b2" };
      return `<div class="stat"><div class="k" style="color:${meta.color}">${c}</div>
              <div class="v">${fmt(totals[c] ?? 0)}</div></div>`;
    }).join("");
  }

  const es = new EventSource(`/sim/${jobId}/stream`);
  es.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    if (ev.type === "start") {
      horizon = ev.horizon; fromDay = ev.from_day || 0;
      ofEl.textContent = horizon;
      if (ev.compartments) initChart(ev.compartments);
      setStatus("running", "running");
    } else if (ev.type === "day") {
      if (!order.length && ev.totals) initChart(Object.keys(ev.totals));
      pushDay(ev.day, ev.totals);
    } else if (ev.type === "done") {
      bar.style.width = "100%";
      setStatus("done", "done");
      es.close();
      setTimeout(() => window.location.reload(), 600); // swap in the full results view
    } else if (ev.type === "failed") {
      setStatus("failed", "failed");
      statusEl.insertAdjacentHTML("afterend",
        `<div class="alert-err" style="margin-top:1rem">Run failed: ${ev.error || "see worker logs"}</div>`);
      es.close();
    } else if (ev.type === "interrupted") {
      setStatus("interrupted", "interrupted");
      es.close();
    }
  };
  es.onerror = () => setStatus("reconnecting…", "queued");
}

window.startMonitor = startMonitor;
