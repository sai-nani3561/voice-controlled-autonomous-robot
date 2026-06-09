# (Voice-Controlled and Autonomous Mobile Robot with Safety-Priority Navigation)

from flask import Flask, request, jsonify, render_template_string
from picarx import Picarx
import threading, time
import csv
from datetime import datetime

app = Flask(__name__)
px = Picarx()

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = f"robot_log_{timestamp}.csv"

with open(LOG_FILE, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Time", "Mode", "Command", "Speed", "Distance", "Event"])

last_log_time = 0

def log_data(event=""):
    global last_log_time

    if event:
        pass
    else:
        if time.time() - last_log_time < 0.5:
            return

    last_log_time = time.time()

    try:
        with open(LOG_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime("%H:%M:%S"),
                mode,
                current_command,
                target_speed,
                distance,
                event
            ])
    except:
        pass

STEERING_OFFSET = -5
px.set_dir_servo_angle(STEERING_OFFSET)

mode = "manual"
emergency_stop = False
distance = 100

current_command = "stop"
target_speed = 40

SAFE_DISTANCE = 25
CLIFF_THRESHOLD = 200

def is_cliff():
    try:
        gs = px.get_grayscale_data()
        if gs[0] < CLIFF_THRESHOLD or gs[1] < CLIFF_THRESHOLD or gs[2] < CLIFF_THRESHOLD:
            return True
    except:
        pass
    return False

def distance_loop():
    global distance
    while True:
        try:
            d = px.ultrasonic.read()
            if d and d > 0:
                distance = d
        except:
            pass
        time.sleep(0.1)

def control_loop():
    global current_command

    while True:

        if emergency_stop:
            px.stop()
            log_data("EMERGENCY ACTIVE")
            time.sleep(0.05)
            continue

        if is_cliff():
            px.stop()
            px.backward(40)
            log_data("CLIFF DETECTED")
            time.sleep(0.5)
            current_command = "stop"
            continue

        if mode == "auto":
            auto_drive()
            log_data("AUTO MODE")
            time.sleep(0.05)
            continue

        if current_command == "forward":
            px.set_dir_servo_angle(STEERING_OFFSET)
            px.forward(target_speed)

        elif current_command == "backward":
            px.backward(target_speed)

        elif current_command == "left":
            px.set_dir_servo_angle(-30)
            px.forward(target_speed)

        elif current_command == "right":
            px.set_dir_servo_angle(30)
            px.forward(target_speed)

        else:
            px.stop()

        log_data()
        time.sleep(0.05)

def auto_drive():
    global distance

    if is_cliff():
        px.stop()
        px.backward(40)
        log_data("AUTO CLIFF")
        time.sleep(1)
        return

    if distance > SAFE_DISTANCE:
        px.set_dir_servo_angle(STEERING_OFFSET)
        px.forward(target_speed)
        return

    px.stop()
    px.backward(50)
    time.sleep(1.8)
    px.stop()

    px.set_dir_servo_angle(-40)
    time.sleep(0.4)
    left = px.ultrasonic.read() or 0

    px.set_dir_servo_angle(40)
    time.sleep(0.4)
    right = px.ultrasonic.read() or 0

    log_data("AUTO AVOID")

    if left > right:
        px.set_dir_servo_angle(-30)
    else:
        px.set_dir_servo_angle(30)

    px.forward(target_speed)
    time.sleep(1)

@app.route('/')
def home():
    return render_template_string(HTML)

@app.route('/control')
def control():
    global current_command
    current_command = request.args.get("cmd", "stop")
    log_data("CMD: " + str(current_command))
    return "OK"

@app.route('/mode')
def set_mode():
    global mode
    mode = request.args.get("m")
    log_data("MODE: " + str(mode))
    return "OK"

@app.route('/speed')
def speed():
    global target_speed
    val = request.args.get("val")
    if val:
        target_speed = int(val)
        log_data("SPEED CHANGE")
    return "OK"

@app.route('/status')
def status():
    return jsonify({"distance": distance})

@app.route('/emergency')
def emergency():
    global emergency_stop
    emergency_stop = True
    px.stop()
    log_data("EMERGENCY STOP")
    return "STOP"

@app.route('/resume')
def resume():
    global emergency_stop
    emergency_stop = False
    log_data("RESUME")
    return "OK"

@app.route('/log_voice')
def log_voice():
    cmd = request.args.get("cmd", "")
    log_data("VOICE: " + cmd)
    return "OK"

threading.Thread(target=distance_loop, daemon=True).start()
threading.Thread(target=control_loop, daemon=True).start()

HTML = """
<!DOCTYPE html>
<html>
<head>
<style>
body {
 background: radial-gradient(circle,#0f2027,#203a43,#2c5364);
 color:white;text-align:center;font-family:Arial;
}
button {
 padding:15px;margin:5px;font-size:18px;border-radius:10px;
}
.joy {
 width:200px;height:200px;background:#111;
 border-radius:50%;margin:auto;position:relative;
}
.knob {
 width:70px;height:70px;background:#00ffcc;
 border-radius:50%;position:absolute;top:65px;left:65px;
}
</style>
</head>

<body>

<h2>🤖 Robot Control</h2>
<div id="speech">Say "hello"</div>
<h3 id="dist"></h3>

<button onclick="setMode('manual')">Manual</button>
<button onclick="setMode('auto')">Auto</button>
<button onclick="startVoice()">Voice</button>

<br><br>

<button onclick="send('forward')">⬆</button><br>
<button onclick="send('left')">⬅</button>
<button onclick="send('stop')">⛔</button>
<button onclick="send('right')">➡</button><br>
<button onclick="send('backward')">⬇</button>

<br><br>

<input type="range" min="20" max="70" value="40" id="speedSlider">

<br><br>

<div class="joy" id="joy">
<div class="knob" id="knob"></div>
</div>

<br><br>

<button onclick="fetch('/emergency')">EMERGENCY</button>
<button onclick="fetch('/resume')">RESUME</button>

<script>
let active=false;
let currentMode="manual";
let lastCmd="";
let lastMove=0;

function send(c){
 if(lastCmd!==c){
  fetch('/control?cmd='+c);
  lastCmd=c;
 }
}

function setMode(m){
 currentMode=m;
 fetch('/mode?m='+m);
}

setInterval(()=>{
 fetch('/status').then(r=>r.json()).then(d=>{
  document.getElementById("dist").innerHTML="Distance: "+d.distance+" cm";
 });
},200);

// VOICE (ONLY MODIFIED PART)
function startVoice(){
 let r=new (window.SpeechRecognition||window.webkitSpeechRecognition)();
 r.continuous=true;
 r.start();

 r.onresult=e=>{

  let c=e.results[e.results.length-1][0].transcript.toLowerCase().trim();

  document.getElementById("speech").innerHTML="You said: "+c;

  fetch('/log_voice?cmd='+encodeURIComponent(c));

  // STRICT WAKE WORD
  if(!active){
    if(c === "hello"){
      active = true;
      setMode("voice");
      speak("I am active");
    } else {
      speak("wrong command");
    }
    return;
  }

  // COMMAND FEEDBACK
  if(c.includes("auto")){
    setMode("auto");
    speak("auto mode activated");
  }
  else if(c.includes("manual")){
    setMode("manual");
    speak("manual mode activated");
  }
  else if(c.includes("forward")){
    send("forward");
    speak("moving forward");
  }
  else if(c.includes("back")){
    send("backward");
    speak("moving backward");
  }
  else if(c.includes("left")){
    send("left");
    speak("turning left");
  }
  else if(c.includes("right")){
    send("right");
    speak("turning right");
  }
  else if(c.includes("stop")){
    send("stop");
    speak("stopping");
  }
  else{
    speak("wrong command");
  }

 };

 function speak(t){
  speechSynthesis.cancel();
  setTimeout(()=>{
    speechSynthesis.speak(new SpeechSynthesisUtterance(t));
  },100);
 }
}

// JOYSTICK (UNCHANGED)
let joy=document.getElementById("joy");
let knob=document.getElementById("knob");

joy.addEventListener("touchmove",e=>{
 let now=Date.now();
 if(now-lastMove<100) return;
 lastMove=now;

 let t=e.touches[0];
 let rect=joy.getBoundingClientRect();

 let x=t.clientX-rect.left-100;
 let y=t.clientY-rect.top-100;

 knob.style.left=(x+100)+"px";
 knob.style.top=(y+100)+"px";

 if(y<-30) send("forward");
 else if(y>30) send("backward");
 else if(x<-30) send("left");
 else if(x>30) send("right");
});

joy.addEventListener("touchend",()=>{
 knob.style.left="65px";
 knob.style.top="65px";
 send("stop");
});

document.getElementById("speedSlider").oninput=function(){
 fetch('/speed?val='+this.value);
};
</script>

</body>
</html>
"""

app.run(host="0.0.0.0", port=5000)