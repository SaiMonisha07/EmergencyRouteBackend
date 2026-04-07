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


def on_disconnect(client, userdata, rc):
    global mqtt_connected
    mqtt_connected = False
    print("⚠️ MQTT Disconnected")


mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect


def connect_mqtt():
    global mqtt_connected

    if not mqtt_connected:
        try:
            print("🔄 Connecting to MQTT...")
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            mqtt_client.loop_start()
            time.sleep(1)   # 🔥 important
        except Exception as e:
            print("❌ MQTT Connect Error:", e)


# Initial connect
connect_mqtt()

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
        connect_mqtt()  # 🔥 ensure connection

        print(f"🔥 Sending → {topic} : {message}")

        # 🔥 send multiple times (important for public broker)
        for i in range(3):
            mqtt_client.publish(topic, message)
            time.sleep(0.1)

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