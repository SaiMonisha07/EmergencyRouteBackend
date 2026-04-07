from flask import Flask, request, jsonify
import json
from geopy.distance import geodesic
import paho.mqtt.client as mqtt
import threading

app = Flask(__name__)

# ===== LOAD RSU DATA =====
with open("rsu_data.json") as f:
    RSU_DATA = json.load(f)

RSU_RANGE = 1000

# ===== MQTT (WEBSOCKETS) =====
mqtt_client = mqtt.Client(transport="websockets")

def on_connect(client, userdata, flags, rc):
    print("✅ MQTT Connected:", rc)

mqtt_client.on_connect = on_connect

mqtt_client.connect("broker.hivemq.com", 8000, 60)
mqtt_client.loop_start()

# ===== MQTT SEND =====
def send_mqtt(topic, message):
    try:
        print(f"📡 Sending → {topic} : {message}")
        mqtt_client.publish(topic, message, qos=1)
    except Exception as e:
        print("❌ MQTT Error:", e)

def send_async(topic, message):
    threading.Thread(target=send_mqtt, args=(topic, message)).start()

# ===== API =====
@app.route("/get_rsus", methods=["POST"])
def get_rsus():

    data = request.json
    route = data.get("route", [])

    print("📥 Route points:", len(route))

    activated = []

    for rsu in RSU_DATA:

        rsu_point = (rsu["lat"], rsu["lon"])
        min_dist = float("inf")
        closest = None

        for p in route:
            d = geodesic(rsu_point, (p["lat"], p["lng"])).meters
            if d < min_dist:
                min_dist = d
                closest = p

        if min_dist <= RSU_RANGE:
            direction = closest.get("direction", "STRAIGHT")

            topic = f"rsu/{rsu['id']}/control"

            print(f"🚦 RSU {rsu['id']} → {direction}")

            send_async(topic, direction)

            activated.append(rsu)

    return jsonify({"rsus_on_route": activated})

# ===== RUN =====
if __name__ == "__main__":
    app.run()