from PySide6.QtCore import Slot
from PySide6.QtWebEngineWidgets import QWebEngineView


class MapWidget(QWebEngineView):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setMinimumSize(400, 300)

        self._map_ready = False
        self._first_position = True

        self.loadFinished.connect(self._on_load_finished)

        self.setHtml(self._create_map_html())

    def _create_map_html(self):

        html = """
<!DOCTYPE html>
<html>

<head>

<meta charset="utf-8">

<meta name="viewport"
      content="width=device-width,
      initial-scale=1.0,
      maximum-scale=1.0,
      user-scalable=no">

<link rel="stylesheet"
      href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<style>

html, body {
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 0;
}

#map {
    width: 100%;
    height: 100%;
}

/* Balloon marker */
.balloon-marker {
    font-size: 34px;
    line-height: 34px;
    text-align: center;
    width: 40px;
    height: 40px;
    transform: translate(-4px, -4px);
}

/* Launch marker */
.launch-marker {
    font-size: 28px;
    line-height: 28px;
    text-align: center;
    width: 34px;
    height: 34px;
}

</style>

</head>

<body>

<div id="map"></div>

<script>

var map = L.map('map').setView([8.5, 76.95], 8);

L.tileLayer(
    'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
    }
).addTo(map);


/* =========================================================
   BALLOON MARKER
   ========================================================= */

var balloonMarker = L.marker(
    [8.5, 76.95],
    {
        icon: L.divIcon({
            className: '',
            html: '<div class="balloon-marker">🎈</div>',
            iconSize: [40, 40],
            iconAnchor: [20, 35]
        })
    }
);


/* =========================================================
   LAUNCH MARKER
   ========================================================= */

var launchMarker = null;


/* =========================================================
   FLIGHT PATH
   ========================================================= */

var flightPath = L.polyline(
    [],
    {
        weight: 4,
        opacity: 0.8
    }
).addTo(map);


/* =========================================================
   UPDATE BALLOON
   ========================================================= */

function updateBalloon(lat, lon)
{
    var position = [lat, lon];

    /*
     * First received GPS position becomes
     * the launch/reference position.
     */

    if (launchMarker === null)
    {
        launchMarker = L.marker(
            position,
            {
                icon: L.divIcon({
                    className: '',
                    html: '<div class="launch-marker">🚀</div>',
                    iconSize: [34, 34],
                    iconAnchor: [17, 30]
                })
            }
        )
        .addTo(map)
        .bindPopup("Launch / First GPS Position");

        launchMarker.openPopup();
    }


    /*
     * Create balloon marker at first position.
     */

    if (!map.hasLayer(balloonMarker))
    {
        balloonMarker
            .setLatLng(position)
            .addTo(map)
            .bindPopup("🎈 HAB Balloon");
    }
    else
    {
        balloonMarker.setLatLng(position);
    }


    /*
     * Add position to flight trajectory.
     */

    flightPath.addLatLng(position);


    /*
     * Automatically follow balloon.
     */

    map.setView(position, map.getZoom());
}


/* =========================================================
   CLEAR TRACK
   ========================================================= */

function clearFlightPath()
{
    flightPath.setLatLngs([]);

    if (launchMarker !== null)
    {
        map.removeLayer(launchMarker);
        launchMarker = null;
    }

    if (map.hasLayer(balloonMarker))
    {
        map.removeLayer(balloonMarker);
    }
}

</script>

</body>
</html>
"""

        return html


    @Slot(bool)
    def _on_load_finished(self, ok):

        if ok:
            self._map_ready = True


    def update_position(self, latitude, longitude):

        if not self._map_ready:
            return

        try:
            latitude = float(latitude)
            longitude = float(longitude)

        except (TypeError, ValueError):
            return

        if not (-90 <= latitude <= 90):
            return

        if not (-180 <= longitude <= 180):
            return

        javascript = (
            f"updateBalloon({latitude}, {longitude});"
        )

        self.page().runJavaScript(javascript)


    def clear_track(self):

        if not self._map_ready:
            return

        self.page().runJavaScript(
            "clearFlightPath();"
        )
