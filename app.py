from flask import Flask, request, jsonify
import json
from geopy.distance import geodesic
import paho.mqtt.client as mqtt
import time
import threading
import os

app = Flask(__name__)

# ===== LOAD RSU DATA =====
with open("rsu_data.json") as f:
    RSU_DATA = json.load(f)

RSU_RANGE = 300

# ===== MQTT CONFIG =====
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

mqtt_client = mqtt.Client()
mqtt_connected = False


# ===== MQTT CALLBACKS =====
def on_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        print("✅ MQTT Connected to HiveMQ")
    else:
        print("❌ MQTT Connection failed:", rc)


def on_disconnect(client, userdata, rc):
    global mqtt_connected
    mqtt_connected = False
    print("⚠️ MQTT Disconnected. Reconnecting...")


mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect


# ===== MQTT BACKGROUND LOOP =====
def mqtt_loop():
    while True:
        try:
            if not mqtt_connected:
                print("🔄 Connecting to MQTT...")
                mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
                mqtt_client.loop_start()
            time.sleep(5)
        except Exception as e:
            print("❌ MQTT Error:", e)
            time.sleep(5)


# Start MQTT thread
threading.Thread(target=mqtt_loop, daemon=True).start()


@app.route("/")
def home():
    return "🚑 Emergency Route Backend Running on Render"


# ===== MQTT PUBLISH =====
def publish_mqtt(topic, message):
    try:
        if mqtt_connected:
            mqtt_client.publish(topic, message, qos=1, retain=False)
            print(f"📡 Sent → {topic} : {message}")
        else:
            print("❌ MQTT not connected, message not sent")
    except Exception as e:
        print("❌ Publish Error:", e)


# ===== MAIN API =====
@app.route("/get_rsus", methods=["POST"])
def get_rsus():

    data = request.json
    route = data["route"]

    activated_rsus = []
    activated_ids = set()

    for rsu in RSU_DATA:

        rsu_point = (rsu["lat"], rsu["lon"])

        min_distance = float("inf")
        closest_point = None

        for point in route:
            route_point = (point["lat"], point["lng"])
            distance = geodesic(rsu_point, route_point).meters

            if distance < min_distance:
                min_distance = distance
                closest_point = point

        if min_distance <= RSU_RANGE and rsu["id"] not in activated_ids:

            direction = closest_point.get("direction", "STRAIGHT")

            rsu["direction"] = direction
            activated_rsus.append(rsu)
            activated_ids.add(rsu["id"])

            topic = f"rsu/{rsu['id']}/control"

            print(f"🚦 Activating RSU {rsu['id']} → {direction}")

            # 🔥 small delay ensures broker stability
            publish_mqtt(topic, direction)
            time.sleep(0.2)

    return jsonify({
        "rsus_on_route": activated_rsus,
        "total": len(activated_rsus)
    })


# ===== RENDER PORT FIX =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)