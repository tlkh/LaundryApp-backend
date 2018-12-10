import firebase_admin
from firebase_admin import credentials
from firebase_admin import messaging
from firebase_admin import db

import time
import flask
from threading import Thread
from datetime import timezone, datetime


class event_loop():

    def __init__(self):
        # Initiate properties
        self.cred = credentials.Certificate(
            'is1d-laundry-firebase-adminsdk.json')
        firebase_admin.initialize_app(self.cred, {
            'databaseURL': 'https://is1d-laundry.firebaseio.com'
        })
        self.to_notify = []
        self.stopped = False

    def start(self):
        self.start_time = time.time()
        Thread(target=self.update, args=()).start()
        return self

    def update(self):
        # keep looping infinitely until the thread is stopped
        global strip, yellow, green
        while True:
            if self.stopped:
                return
            else:
                self.checkButtonPresses()
                time.sleep(1)
                self.checkCompleted()
                time.sleep(1)

    def stop(self):
        self.stopped = True

    def build_android_message(self, topic_name, message):
        message = messaging.Message(
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    title='Laundry Notification',
                    body=str(message),
                ),
            ),
            topic=topic_name,
        )
        return message

    def send_message(self, topic_name, message):
        message_data = self.build_android_message(topic_name, message)
        response = messaging.send(message_data)
        print(response)

    def getUnixTime(self):
        return int(datetime.now(tz=timezone.utc).timestamp())

    def getMachineRef(self, block, machineid):
        block_ref = db.reference("/"+block+"/")
        if machineid[0] == "W":
            machine_ref = block_ref.child("washers").child(machineid)
        elif machineid[0] == "D":
            machine_ref = block_ref.child("dryers").child(machineid)
        else:
            print("[ERROR] Invalid machine id")
            return False
        return machine_ref

    def updateMachineStartTime(self, block, machineid):
        machine_ref = self.getMachineRef(block, machineid)
        unixtime = self.getUnixTime()
        machine_ref.child("startTime").set(unixtime-5)
        machine_ref.child("collected").set("false")

        topic_name = machine_ref.child("topicName").get()
        if topic_name not in self.to_notify:
            self.to_notify.append(topic_name)

        return True

    def resetScratch(self, block, machineid):
        block_ref = db.reference("/scratch/"+block+"/")
        if machineid[0] == "W":
            machine_ref = block_ref.child("washers").child(machineid)
        elif machineid[0] == "D":
            machine_ref = block_ref.child("dryers").child(machineid)
        else:
            print("[ERROR] Invalid machine id", machineid)
            return False

        machine_ref.child("btnCollect").set(0)
        machine_ref.child("btnStart").set(0)

    def updateMachineCollectedState(self, block, machineid):
        machine_ref = self.getMachineRef(block, machineid)

        topic_name = machine_ref.child("topicName").get()
        print("Sending to:", topic_name)
        block_no, machine_type, mid = topic_name.split("_")
        message_body = "Block "+block_no+" "+machine_type.capitalize()+mid + \
            " Machine Available"
        self.send_message(topic_name, message_body)

        machine_ref.child("collected").set("true")
        return True

    def notifyMachineEnded(self, topic_name):
        print("Sending to:", topic_name)
        block_no, machine_type, mid = topic_name.split("_")
        message_body = "Block "+block_no+" "+machine_type.capitalize()+mid + \
            " Machine Cycle Ended"
        self.send_message(topic_name, message_body)
        return True

    def checkButtonPresses(self):
        scratch = db.reference('/scratch/').get()

        for block in scratch:
            # washers
            for washer in scratch[block]["washers"]:
                washer_scratch = scratch[block]["washers"][washer]
                started = int(washer_scratch["btnStart"])
                collected = int(washer_scratch["btnCollect"])

                if started == 1:
                    self.updateMachineStartTime(block, washer)
                    self.resetScratch(block, washer)

                if collected == 1:
                    self.updateMachineCollectedState(block, washer)
                    self.resetScratch(block, washer)

            # dryers
            for dryer in scratch[block]["dryers"]:
                dryer_scratch = scratch[block]["dryers"][dryer]
                started = int(dryer_scratch["btnStart"])
                collected = int(dryer_scratch["btnCollect"])

                if started == 1:
                    self.updateMachineStartTime(block, dryer)
                    self.resetScratch(block, dryer)

                if collected == 1:
                    self.updateMachineCollectedState(block, dryer)
                    self.resetScratch(block, dryer)

    def fastForward(self, block, machineid):
        machine_ref = self.getMachineRef(block, machineid)
        unixtime = self.getUnixTime()
        machine_ref.child("startTime").set(int(unixtime-45*60+20))
        return True

    def startMachine(self, block, machineid):
        if machineid == "allw":
            for i in range(1,10):
                self.startMachine(block, "W0"+str(i))
            for i in range(10,13):
                self.startMachine(block, "W"+str(i))
        elif machineid == "alld":
            for i in range(1,10):
                self.startMachine(block, "D0"+str(i))
        else:
            machine_ref = self.getMachineRef(block, machineid)
            unixtime = self.getUnixTime()
            machine_ref.child("startTime").set(unixtime-5)
            machine_ref.child("collected").set("false")

            topic_name = machine_ref.child("topicName").get()
            if topic_name not in self.to_notify:
                self.to_notify.append(topic_name)

        return True

    def collectMachine(self, block, machineid, status="true"):
        machine_ref = self.getMachineRef(block, machineid)
        topic_name = machine_ref.child("topicName").get()
        print("Sending to:", topic_name)
        block_no, machine_type, mid = topic_name.split("_")
        message_body = "Block "+block_no+" "+machine_type.capitalize()+mid + \
            " Machine Available"
        self.send_message(topic_name, message_body)

        machine_ref.child("collected").set(status)
        return True

    def checkCompleted(self):
        for block in ["block_55", "block_57", "block_59"]:
            block_data = db.reference("/"+block+"/").get()

            for washer in block_data["washers"]:
                washer_startTime = block_data["washers"][washer]["startTime"]
                time_elapsed = self.getUnixTime() - washer_startTime
                collected = block_data["washers"][washer]["collected"]
                if (time_elapsed > (45*60) and collected == "false"):
                    topic_name = block_data["washers"][washer]["topicName"]
                    if topic_name in self.to_notify:
                        self.notifyMachineEnded(topic_name)
                        self.to_notify.remove(topic_name)

            for dryer in block_data["dryers"]:
                dryer_startTime = block_data["dryers"][dryer]["startTime"]
                collected = block_data["dryers"][dryer]["collected"]
                time_elapsed = self.getUnixTime() - dryer_startTime
                if (time_elapsed > (45*60) and collected == "false"):
                    topic_name = block_data["dryers"][dryer]["topicName"]
                    if topic_name in self.to_notify:
                        self.notifyMachineEnded(topic_name)
                        self.to_notify.remove(topic_name)


fb_event_loop = event_loop().start()

# setup Flask app

app = flask.Flask(__name__)

return_back_page = """
<html>
<hr />
<h1>Success.</h1>
<a href="http://13.229.114.67/">Go back</a>
<hr />
</html>
"""


@app.route("/fast_forward")
def fast_forward():
    global fb_event_loop
    block_number = flask.request.args.get("block")
    machine_id = flask.request.args.get("machine")
    fb_event_loop.fastForward(block_number, machine_id)
    return return_back_page


@app.route("/start")
def start_():
    global fb_event_loop
    block_number = flask.request.args.get("block")
    machine_id = flask.request.args.get("machine")
    fb_event_loop.startMachine(block_number, machine_id)
    fb_event_loop.collectMachine(block_number, machine_id, "false")
    return return_back_page


@app.route("/collect")
def collect_():
    global fb_event_loop
    block_number = flask.request.args.get("block")
    machine_id = flask.request.args.get("machine")
    fb_event_loop.collectMachine(block_number, machine_id)
    return return_back_page


# start Flask server

if __name__ == "__main__":
    print(" * [i] Starting Flask server")
    app.run(host='0.0.0.0', port=5000)
