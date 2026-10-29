
const sourceInput = document.getElementById("source");
const destinationInput = document.getElementById("destination");
const findButton = document.getElementById("findRoute");
const errorMessage = document.getElementById("errorMessage");

const map = L.map("map", {
    zoomControl: false,
    scrollWheelZoom: false
}).setView([40.7580, -73.9855], 13);

L.control.zoom({
    position: "topright"
}).addTo(map);

L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
        attribution: "&copy; OpenStreetMap contributors",
        maxZoom: 19
    }
).addTo(map);

let routeGroup = L.layerGroup().addTo(map);

function markerIcon(letter, color) {
    return L.divIcon({
        className: "custom-marker",
        html: `
            <div class="marker-inner"
                 style="background:${color}">
                ${letter}
            </div>
        `,
        iconSize: [34, 34],
        iconAnchor: [17, 17]
    });
}

document.getElementById("swapLocations").addEventListener(
    "click",
    () => {
        const temp = sourceInput.value;
        sourceInput.value = destinationInput.value;
        destinationInput.value = temp;
    }
);

async function checkBackend() {
    try {
        const response = await fetch("/api/health");
        if (!response.ok) throw new Error("Unavailable");

        document.getElementById("systemStatus").textContent =
            "Connected and ready";
    } catch {
        document.getElementById("systemStatus").textContent =
            "Backend unavailable";
    }
}

checkBackend();

findButton.addEventListener("click", async () => {
    const source = sourceInput.value;
    const destination = destinationInput.value;

    errorMessage.textContent = "";

    if (!source || !destination) {
        errorMessage.textContent =
            "Please choose both locations.";
        return;
    }

    if (source === destination) {
        errorMessage.textContent =
            "Please choose two different locations.";
        return;
    }

    findButton.disabled = true;
    findButton.innerHTML = "Calculating route...";

    try {
        const response = await fetch("/api/route", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                source,
                destination
            })
        });

        const raw = await response.text();

        let data;
        try {
            data = JSON.parse(raw);
        } catch {
            throw new Error("The server returned an invalid response.");
        }

        if (!response.ok) {
            throw new Error(
                data.detail || "Unable to calculate route."
            );
        }

        if (!Array.isArray(data.coordinates) ||
            data.coordinates.length < 2) {
            throw new Error("No valid route coordinates received.");
        }

        updateResults(data);
        drawRoute(data);

    } catch (error) {
        errorMessage.textContent = error.message;
    } finally {
        findButton.disabled = false;
        findButton.innerHTML =
            'Calculate route <span>→</span>';
    }
});

function updateResults(data) {
    document.getElementById("routeText").textContent =
        `${data.source} → ${data.destination}`;

    document.getElementById("routeDescription").textContent =
        "Shortest-distance driving route calculated using the Manhattan road network.";

    document.getElementById("sourceName").textContent =
        data.source;

    document.getElementById("destinationName").textContent =
        data.destination;

    document.getElementById("distanceValue").textContent =
        Number(data.distance_km).toFixed(2);

    document.getElementById("timeValue").textContent =
        Number(data.estimated_minutes).toFixed(1);

    const badge = document.getElementById("resultBadge");
    badge.textContent = "ROUTE CALCULATED";
    badge.classList.add("ready");
}

function drawRoute(data) {
    routeGroup.clearLayers();

    const coordinates = data.coordinates;

    // White outline
    L.polyline(coordinates, {
        color: "#ffffff",
        weight: 12,
        opacity: 0.95,
        lineCap: "round",
        lineJoin: "round"
    }).addTo(routeGroup);

    // Main route
    const routeLine = L.polyline(coordinates, {
        color: "#2f7354",
        weight: 7,
        opacity: 1,
        lineCap: "round",
        lineJoin: "round"
    }).addTo(routeGroup);

    L.marker(data.start, {
        icon: markerIcon("A", "#42996e")
    })
    .bindPopup(`Starting point: ${data.source}`)
    .addTo(routeGroup);

    L.marker(data.end, {
        icon: markerIcon("B", "#d39b61")
    })
    .bindPopup(`Destination: ${data.destination}`)
    .addTo(routeGroup);

    setTimeout(() => {
        map.invalidateSize();

        map.fitBounds(routeLine.getBounds(), {
            padding: [65, 65],
            maxZoom: 16,
            animate: true
        });
    }, 150);
}
