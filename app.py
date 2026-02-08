# © 2026 Richa Gupta. All Rights Reserved.
# Attendance Management System Project
# Developed by Richa Gupta


from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash
import sqlite3, os, math, random
from datetime import datetime, time, timedelta

app = Flask(__name__)
app.secret_key = "secret123"
now = datetime.now()


#PATHS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "attendance.db")

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

#COLLEGE LOCATION

# COLLEGE_LAT = 22.351174
# COLLEGE_LON = 82.697461
# ALLOWED_RADIUS_METERS = 500

COLLEGE_LAT = 22.335070
COLLEGE_LON = 82.712939
ALLOWED_RADIUS_METERS = 500


# TIME WINDOWS 

# ENTRY_START = time(8, 0)
# ENTRY_END   = time(8, 30)

# EXIT_START  = time(14, 0)
# EXIT_END    = time(15, 0)


ENTRY_START = (now - timedelta(minutes=10)).time()
ENTRY_END   = (now + timedelta(minutes=10)).time()
EXIT_START  = (now - timedelta(minutes=10)).time()
EXIT_END    = (now + timedelta(minutes=10)).time()


#DATABASE

def get_db():
    con = sqlite3.connect(DB, timeout=10)
    con.execute("PRAGMA journal_mode=WAL;")
    return con

def init_db():
    con = get_db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fname TEXT,
        lname TEXT,
        email TEXT UNIQUE,
        password TEXT,
        otp INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date TEXT,
        type TEXT,
        time TEXT,
        state TEXT,
        city TEXT,
        photo TEXT
    )
    """)

    con.commit()
    con.close()

init_db()


#DISTANCE 
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))




#LOGIN
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        con = get_db()
        cur = con.cursor()
        cur.execute("SELECT id,fname FROM users WHERE email=? AND password=?",
                    (email, password))
        user = cur.fetchone()
        con.close()

        if user:
            session["user_id"] = user[0]
            session["name"] = user[1]
            return redirect("/dashboard")
        else:
            flash("Invalid email or password", "error")

    return render_template("login.html")


#REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        fname = request.form["fname"]
        lname = request.form["lname"]
        email = request.form["email"]
        password = request.form["password"]

        con = get_db()
        try:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO users (fname,lname,email,password) VALUES (?,?,?,?)",
                (fname, lname, email, password)
            )
            con.commit()

            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login")) 

        except sqlite3.IntegrityError:
            flash("Email already registered", "error")

        finally:
            con.close()

    return render_template("register.html")




#FORGOT PASSWORD
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]

        con = sqlite3.connect(DB)
        cur = con.cursor()
        cur.execute("SELECT id FROM users WHERE email=?", (email,))
        user = cur.fetchone()
        con.close()

        if user:
            otp = str(random.randint(100000, 999999))
            session["reset_otp"] = otp
            session["reset_email"] = email

            print("OTP for password reset:", otp)  

            
            return redirect(url_for("verify_otp"))
        else:
            flash("Email not registered", "error")

    return render_template("forgot_password.html")



@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if "reset_otp" not in session:
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        otp = request.form["otp"]
        print("User entered OTP:", otp)
        print("Session OTP:", session["reset_otp"])

        if otp == session["reset_otp"]:
            flash("OTP verified successfully", "success")
            return redirect(url_for("reset_password"))
        else:
            flash("Invalid OTP", "error")
           
            return render_template(
                "verify_otp.html",
                debug_otp=session.get("reset_otp")
            )

   
    flash("OTP sent! Check console.", "success")

    return render_template(
        "verify_otp.html",
        debug_otp=session.get("reset_otp")
    )



# RESET PASSWORD 
@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if "reset_email" not in session:
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form["password"]
        email = session["reset_email"]

        con = sqlite3.connect(DB)
        cur = con.cursor()
        cur.execute("UPDATE users SET password=? WHERE email=?", (password, email))
        con.commit()
        con.close()

        session.pop("reset_otp", None)
        session.pop("reset_email", None)

        flash("Password updated successfully", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html")

# DASHBOARD
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")
    return render_template("dashboard.html", name=session["name"])

#ENTRY 
@app.route("/entry", methods=["GET", "POST"])
@app.route("/exit", methods=["GET", "POST"])
def attendance():
    if "user_id" not in session:
        return redirect("/login")

    att_type = "ENTRY" if request.path == "/entry" else "EXIT"
    now_time = datetime.now().time()

    if request.method == "POST":
        date_val = request.form["date"]
        state = request.form["state"]
        city = request.form["city"]
        lat = float(request.form["lat"])
        lon = float(request.form["lon"])
        photo = request.files["photo"]

        if att_type == "ENTRY" and not (ENTRY_START <= now_time <= ENTRY_END):
            flash("Entry time window closed", "error")
            return redirect(request.path)

        if att_type == "EXIT" and not (EXIT_START <= now_time <= EXIT_END):
            flash("Exit time window closed", "error")
            return redirect(request.path)

        
        distance = calculate_distance(lat, lon, COLLEGE_LAT, COLLEGE_LON)

        if distance > ALLOWED_RADIUS_METERS:
            flash(" You are not in the college location", "error")
            return render_template("attendance.html", name=session["name"])


        filename = f"{session['user_id']}_{int(datetime.now().timestamp())}.jpg"
        photo.save(os.path.join(UPLOAD_FOLDER, filename))

        con = get_db()
        cur = con.cursor()
        cur.execute("""
            INSERT INTO attendance (user_id,date,type,time,state,city,photo)
            VALUES (?,?,?,?,?,?,?)
        """, (
            session["user_id"],
            date_val,
            att_type,
            datetime.now().strftime("%H:%M:%S"),
            state,
            city,
            filename
        ))
        con.commit()
        con.close()

        session.update({
            "success_date": date_val,
            "success_state": state,
            "success_city": city,
            "success_photo": filename
        })

        return redirect("/success")

    return render_template("attendance.html", name=session["name"])
#record
@app.route("/record")
def record():

    
    if "user_id" not in session:
        flash("Please login first", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
        SELECT date, type, time, state, city
        FROM attendance
        WHERE user_id = ?
        ORDER BY date DESC, time DESC
    """, (user_id,))

    data = cur.fetchall()
    conn.close()

    return render_template("record.html", data=data)


#SUCCESS
@app.route("/success")
def success():
    return render_template(
        "success.html",
        name=session.get("name"),
        date=session.get("success_date"),
        state=session.get("success_state"),
        city=session.get("success_city"),
        photo=session.get("success_photo")
    )

#LOGOUT

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run(debug=True)

