from flask import Flask, request, jsonify
import json
from geopy.distance import geodesic
import paho.mqtt.client as mqtt

# ================= MQTT SETUP =================
mqtt_client = mqtt.Client()
mqtt_client.connect("broker.hivemq.com", 1883, 60)
mqtt_client.loop_start()

# ================= FLASK APP =================
app = Flask(__name__)

# ================= LOAD RSU DATA =================
with open("rsu_data.json") as f:
    RSU_DATA = json.load(f)

# Distance threshold (meters)
RSU_RANGE = 300


@app.route("/")
def home():
    return "Emergency Route Backend Running"


# ================= MAIN API =================
@app.route("/get_rsus", methods=["POST"])
def get_rsus():

    data = request.json
    route = data["route"]

    activated_rsus = []
    activated_ids = set()

    for rsu in RSU_DATA:

        rsu_point = (rsu["lat"], rsu["lon"])

        closest_point = None
        min_distance = float("inf")

        # 🔍 Find closest route point
        for point in route:
            route_point = (point["lat"], point["lng"])
            distance = geodesic(rsu_point, route_point).meters

            if distance < min_distance:
                min_distance = distance
                closest_point = point

        # ✅ Activate RSU if within range
        if min_distance <= RSU_RANGE and rsu["id"] not in activated_ids:

            direction = closest_point.get("direction", "STRAIGHT")

            rsu["direction"] = direction
            activated_rsus.append(rsu)
            activated_ids.add(rsu["id"])

            topic = f"rsu/{rsu['id']}/control"

            print(f"🚦 Activating RSU {rsu['id']} → {direction}")

            mqtt_client.publish(topic, direction)

    return jsonify({
        "rsus_on_route": activated_rsus,
        "total": len(activated_rsus)
    })


# ================= RUN SERVER =================
if __name__ == "__main__":
    app.run()