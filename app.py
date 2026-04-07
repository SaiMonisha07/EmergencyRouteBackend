from flask import Flask, request, jsonify
import json
from geopy.distance import geodesic
import paho.mqtt.client as mqtt
import time

# ================= MQTT SETUP =================
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

mqtt_client = mqtt.Client()
mqtt_connected = False


def on_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        print("✅ MQTT Connected to HiveMQ")
    else:
        print("❌ MQTT Failed:", rc)


mqtt_client.on_connect = on_connect

# 🔥 CONNECT + WAIT
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

# 🔥 WAIT UNTIL CONNECTED
while not mqtt_connected:
    print("⏳ Waiting for MQTT connection...")
    time.sleep(0.5)


# ================= FLASK APP =================
app = Flask(__name__)

# ================= LOAD RSU DATA =================
with open("rsu_data.json") as f:
    RSU_DATA = json.load(f)

RSU_RANGE = 300


@app.route("/")
def home():
    return "Emergency Route Backend Running"


# ================= MQTT PUBLISH =================
def publish_mqtt(topic, message):
    try:
        print(f"📡 Sending → {topic} : {message}")

        # 🔥 ensure delivery
        result = mqtt_client.publish(topic, message)
        result.wait_for_publish()

    except Exception as e:
        print("❌ MQTT Error:", e)


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

        for point in route:
            route_point = (point["lat"], point["lng"])
            distance = geodesic(rsu_point, route_point).meters

            if distance < min_distance:
                min_distance = distance
                closest_point = point

        if min_distance <= RSU_RANGE and rsu["id"] not in activated_ids:

            direction = closest_point.get("direction", "STRAIGHT").upper()

            rsu["direction"] = direction
            activated_rsus.append(rsu)
            activated_ids.add(rsu["id"])

            topic = f"rsu/{rsu['id']}/control"

            print(f"🚦 Activating RSU {rsu['id']} → {direction}")

            publish_mqtt(topic, direction)

    return jsonify({
        "rsus_on_route": activated_rsus,
        "total": len(activated_rsus)
    })


# ================= RUN SERVER =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)