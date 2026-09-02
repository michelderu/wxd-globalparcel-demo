const map = L.map("routeMap", { zoomControl: true });
L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  attribution: "&copy; OpenStreetMap contributors &copy; CARTO"
}).addTo(map);
const routeLayer = L.layerGroup().addTo(map);
map.setView([20, 0], 2);

function formatGeo(geo) {
  if (!geo || geo.latitude == null || geo.longitude == null) {
    return "-";
  }
  return `${geo.latitude.toFixed(4)}, ${geo.longitude.toFixed(4)}`;
}

function renderMap(rows) {
  routeLayer.clearLayers();
  const points = rows
    .map((row) => ({
      lat: row.geo_position?.latitude,
      lon: row.geo_position?.longitude,
      status: row.status,
      event_ts: row.event_ts,
      hub_code: row.hub_code
    }))
    .filter((p) => p.lat != null && p.lon != null);

  if (!points.length) {
    map.setView([20, 0], 2);
    return;
  }

  const chronological = [...points].reverse();
  const latLngs = chronological.map((p) => [p.lat, p.lon]);
  L.polyline(latLngs, { color: "#60a5fa", weight: 3, opacity: 0.8 }).addTo(routeLayer);

  chronological.forEach((p, idx) => {
    const isLatest = idx === chronological.length - 1;
    L.circleMarker([p.lat, p.lon], {
      radius: isLatest ? 7 : 5,
      color: isLatest ? "#4ade80" : "#93c5fd",
      fillColor: isLatest ? "#4ade80" : "#60a5fa",
      fillOpacity: 0.9,
      weight: 1
    })
      .bindPopup(`${p.status}<br>${p.hub_code}<br>${p.event_ts}`)
      .addTo(routeLayer);
  });

  map.fitBounds(latLngs, { padding: [24, 24], maxZoom: 6 });
}

function renderTimeline(parcelId, rows) {
  const tbody = document.getElementById("timelineRows");
  tbody.innerHTML = "";

  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="7">No events found for ${parcelId}. Verify Cassandra partition key.</td></tr>`;
    return;
  }

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    const cols = [
      row.event_ts || "-",
      row.status || "-",
      row.hub_code || "-",
      row.region || "-",
      formatGeo(row.geo_position),
      row.exception_code || "-",
      row.delivery_note || "-"
    ];
    cols.forEach((col) => {
      const td = document.createElement("td");
      td.textContent = col;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

async function loadAuditData() {
  const parcelId = document.getElementById("parcelId").value.trim();
  document.getElementById("summaryParcel").textContent = parcelId;
  const res = await fetch(`/api/audit/${encodeURIComponent(parcelId)}`);
  if (!res.ok) {
    renderTimeline(parcelId, []);
    renderMap([]);
    document.getElementById("truthStatus").textContent = "NOT_FOUND";
    document.getElementById("appStatus").textContent = "UNKNOWN";
    document.getElementById("reconResult").textContent = "Unable to reconcile";
    document.getElementById("reconResult").className = "warn";
    return;
  }
  const data = await res.json();
  const timeline = data.timeline || [];
  renderTimeline(parcelId, timeline);
  renderMap(timeline);

  const summary = data.summary || {};
  document.getElementById("appStatus").textContent = summary.customer_app_status || "UNKNOWN";
  document.getElementById("truthStatus").textContent = summary.cassandra_latest_status || "UNKNOWN";
  document.getElementById("reconResult").textContent = summary.reconciliation_result || "Unknown";
  document.getElementById("reconResult").className = summary.index_lag_suspected ? "warn" : "ok";
}

document.getElementById("loadBtn").addEventListener("click", () => {
  loadAuditData();
});

document.getElementById("resolveBtn").addEventListener("click", () => {
  document.getElementById("reconResult").textContent = "Source-of-truth confirmed - ticket ready to close";
  document.getElementById("reconResult").className = "ok";
});

loadAuditData();
