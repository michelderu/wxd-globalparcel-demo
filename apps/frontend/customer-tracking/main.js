function setError(message) {
  const errorBanner = document.getElementById("errorBanner");
  if (!message) {
    errorBanner.textContent = "";
    errorBanner.classList.add("hidden");
    return;
  }
  errorBanner.textContent = message;
  errorBanner.classList.remove("hidden");
}

function clearTimeline() {
  document.getElementById("timelineRows").innerHTML = "";
}

function formatDate(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function formatFriendlyStepDate(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const now = new Date();
  const dayMs = 24 * 60 * 60 * 1000;
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const diffDays = Math.round((startOfDate.getTime() - startOfToday.getTime()) / dayMs);
  const timePart = date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

  if (diffDays === 0) {
    return `Today, ${timePart}`;
  }
  if (diffDays === -1) {
    return `Yesterday, ${timePart}`;
  }
  if (diffDays === 1) {
    return `Tomorrow, ${timePart}`;
  }
  return date.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
}

function toFriendlyStatus(status) {
  const map = {
    LABEL_CREATED: "Label Created",
    PICKED_UP: "Picked Up",
    SORTED_AT_HUB: "Sorted at Hub",
    IN_TRANSIT: "In Transit",
    OUT_FOR_DELIVERY: "Out for Delivery",
    DELIVERED: "Delivered"
  };
  return map[status] || "Status Updated";
}

function toStatusMessage(status, hub) {
  if (status === "DELIVERED") {
    return "Your package has been delivered.";
  }
  if (status === "OUT_FOR_DELIVERY") {
    return "Great news - your courier is on the way.";
  }
  if (status === "IN_TRANSIT" || status === "SORTED_AT_HUB") {
    return `Your package is moving through our network${hub ? ` via ${hub}` : ""}.`;
  }
  if (status === "PICKED_UP") {
    return "Your package has been picked up and is heading to a hub.";
  }
  if (status === "LABEL_CREATED") {
    return "The shipment has been created and is waiting for pickup.";
  }
  return "Your package has a new update.";
}

function statusRank(status) {
  if (status === "LABEL_CREATED") return 1;
  if (status === "PICKED_UP") return 2;
  if (status === "SORTED_AT_HUB" || status === "IN_TRANSIT") return 3;
  if (status === "OUT_FOR_DELIVERY") return 4;
  if (status === "DELIVERED") return 5;
  return 1;
}

function fillStepDates(rows) {
  const stepConfig = [
    { statuses: ["LABEL_CREATED"], dateId: "stepLabelCreatedDate" },
    { statuses: ["PICKED_UP"], dateId: "stepPickedUpDate" },
    { statuses: ["SORTED_AT_HUB", "IN_TRANSIT"], dateId: "stepInTransitDate" },
    { statuses: ["OUT_FOR_DELIVERY"], dateId: "stepOutForDeliveryDate" },
    { statuses: ["DELIVERED"], dateId: "stepDeliveredDate" }
  ];
  stepConfig.forEach((step) => {
    const match = rows.find((row) => step.statuses.includes(row.status));
    document.getElementById(step.dateId).textContent = formatFriendlyStepDate(match?.event_ts);
  });
}

function updateProgress(status, rows) {
  const rank = statusRank(status);
  const ids = [
    "stepLabelCreated",
    "stepPickedUp",
    "stepInTransit",
    "stepOutForDelivery",
    "stepDelivered"
  ];
  ids.forEach((id, index) => {
    const el = document.getElementById(id);
    if (index < rank) {
      el.className = "step done";
    } else if (index + 1 === rank) {
      el.className = "step active";
    } else {
      el.className = "step";
    }
  });
  fillStepDates(rows || []);
}

function renderTimeline(rows) {
  const container = document.getElementById("timelineRows");
  container.innerHTML = "";

  rows.forEach((row, index) => {
    const item = document.createElement("article");
    item.className = "timeline-item";

    const title = document.createElement("h4");
    title.textContent = toFriendlyStatus(row.status);
    item.appendChild(title);

    const meta = document.createElement("p");
    meta.className = "timeline-meta";
    meta.textContent = `${formatDate(row.event_ts)} - ${row.hub_code || "-"}${row.region ? `, ${row.region}` : ""}`;
    item.appendChild(meta);

    if (row.exception_code) {
      const flag = document.createElement("p");
      flag.className = "timeline-flag";
      flag.textContent = `Service note: ${row.exception_code}`;
      item.appendChild(flag);
    }
    if (row.delivery_note) {
      const note = document.createElement("p");
      note.className = "timeline-meta";
      note.textContent = row.delivery_note;
      item.appendChild(note);
    }

    if (index === 0) {
      item.classList.add("latest");
    }

    container.appendChild(item);
  });
}

function resetSummary() {
  document.getElementById("friendlyStatus").textContent = "Tracking unavailable";
  document.getElementById("statusDetail").textContent = "We could not load your shipment details right now.";
  document.getElementById("summaryParcel").textContent = "-";
  document.getElementById("latestHub").textContent = "-";
  document.getElementById("customerEta").textContent = "-";
  document.getElementById("lastUpdated").textContent = "-";
  updateProgress("", []);
}

function updateSummary(data) {
  const latestStatus = data.latest_status || "UNKNOWN";
  const latestHub = data.latest_hub || "-";
  const latestEventTs = data.latest_event_ts || "";
  document.getElementById("friendlyStatus").textContent = toFriendlyStatus(latestStatus);
  document.getElementById("statusDetail").textContent = toStatusMessage(latestStatus, latestHub);
  document.getElementById("summaryParcel").textContent = data.parcel_id || "-";
  document.getElementById("latestHub").textContent = latestHub;
  document.getElementById("customerEta").textContent = formatDate(data.customer_eta);
  document.getElementById("lastUpdated").textContent = formatDate(latestEventTs);
  updateProgress(latestStatus, data.timeline || []);
}

async function loadParcel() {
  const parcelId = document.getElementById("parcelId").value.trim();
  if (!parcelId) {
    setError("Enter a tracking number.");
    return;
  }

  setError("");
  try {
    const response = await fetch(`/api/customer/${encodeURIComponent(parcelId)}`);
    if (!response.ok) {
      clearTimeline();
      resetSummary();
      if (response.status === 404) {
        setError(`We could not find tracking number ${parcelId}. Please check and try again.`);
        return;
      }
      setError("We are unable to load live tracking updates right now.");
      return;
    }
    const data = await response.json();
    updateSummary(data);
    renderTimeline(data.timeline || []);
  } catch (err) {
    clearTimeline();
    resetSummary();
    setError("Network error while loading tracking updates.");
  }
}

document.getElementById("trackBtn").addEventListener("click", () => {
  loadParcel();
});

document.getElementById("parcelId").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    loadParcel();
  }
});

loadParcel();
setInterval(loadParcel, 3000);
