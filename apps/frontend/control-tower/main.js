function money(value) {
  return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function renderKpis(kpis) {
  const items = [
    { label: "Parcels in view", value: kpis.parcels, cls: "" },
    { label: "In flight", value: kpis.in_flight, cls: "" },
    { label: "Delivered", value: kpis.delivered, cls: "" },
    { label: "SLA at risk", value: kpis.sla_at_risk, cls: kpis.sla_at_risk ? "danger" : "" },
    { label: "Live cost exposure", value: money(kpis.live_cost_exposure), cls: "" }
  ];
  document.getElementById("kpis").innerHTML = items
    .map(
      (item) =>
        `<article class="kpi ${item.cls}"><span>${item.label}</span><strong>${item.value}</strong></article>`
    )
    .join("");
}

function renderStatus(rows) {
  const max = Math.max(1, ...rows.map((r) => r.parcels));
  document.getElementById("statusMix").innerHTML = rows
    .map((row) => {
      const width = Math.round((row.parcels / max) * 100);
      return `<div class="bar-row"><span>${row.status}</span><div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div><span>${row.parcels}</span></div>`;
    })
    .join("");
}

function renderSurcharge(rows) {
  document.getElementById("surcharge").innerHTML = (rows || [])
    .map((row) => `<div><span>${row.region}</span><strong>${Number(row.fuel_surcharge).toFixed(2)}</strong></div>`)
    .join("") || "<div><span>Waiting for surcharge ticks</span><strong>—</strong></div>";
}

function renderHubs(rows) {
  document.getElementById("hubRows").innerHTML = (rows || [])
    .map((row) => {
      const riskClass = row.sla_at_risk ? "risk" : "";
      return `<tr>
        <td>${row.hub_code}<div style="color:var(--muted);font-size:12px">${row.hub_city || ""}</div></td>
        <td>${row.in_flight}</td>
        <td class="${riskClass}">${row.sla_at_risk}</td>
        <td>${row.weather_delays}</td>
        <td>${money(row.exposure)}</td>
      </tr>`;
    })
    .join("");
}

function renderTicker(rows) {
  document.getElementById("ticker").innerHTML = (rows || [])
    .map((row) => {
      const risk = row.sla_risk ? " risk" : "";
      const extra = row.sla_risk ? row.sla_reason : row.delivery_note;
      return `<article class="tick${risk}"><strong>${row.parcel_id} · ${row.status} · ${row.hub_code}</strong><span>${row.event_ts} — ${extra || ""}</span></article>`;
    })
    .join("");
}

async function refresh() {
  try {
    const response = await fetch("/api/snapshot");
    if (!response.ok) throw new Error("snapshot failed");
    const data = await response.json();
    renderKpis(data.kpis || {});
    renderStatus(data.by_status || []);
    renderSurcharge(data.surcharge || []);
    renderHubs(data.by_hub || []);
    renderTicker(data.recent || []);
    document.getElementById("freshness").textContent = `Current view · ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    document.getElementById("freshness").textContent = "Current view not ready yet";
  }
}

refresh();
setInterval(refresh, 2000);
