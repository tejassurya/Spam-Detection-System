from flask import Flask, request, render_template, redirect, url_for, session
import joblib
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret123"

# Load ML model
model = joblib.load("spam_model.pkl")
vectorizer = joblib.load("vectorizer.pkl")



db = sqlite3.connect("spam_detection.db", check_same_thread=False)
cursor = db.cursor()

# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    msg = None
    if request.method == "POST":
        email = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            msg = "Passwords do not match!"
        else:
            hashed_password = generate_password_hash(password)

            cursor.execute(
                "INSERT INTO users (email, username, password) VALUES (?, ?, ?)",
                (email, username, hashed_password)
            )
            db.commit()
            msg = "Registration successful! Please login."

    return render_template("register.html", msg=msg)


# ---------------- LOGIN ----------------
# @app.route("/login", methods=["GET", "POST"])
# def login():
#     error = None
#     if request.method == "POST":
#         email = request.form["email"]
#         password = request.form["password"]

#         cursor.execute("SELECT * FROM users WHERE email=?", (email,))
#         user = cursor.fetchone()

#         if user and check_password_hash(user[3], password):
#             session["user"] = user[1]  # username
#             return redirect(url_for("home"))
#         else:
#             error = "Invalid Email or Password"

#     return render_template("login.html", error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()

        if not user:
            return "Invalid Email or Password"

        # Check if blocked
        if user[4] == 'BLOCKED':
            return "Your account is blocked by admin"

        # Correct password check
        if check_password_hash(user[3], password):
            session["user"] = user[2]   # username
            session["email"] = user[1]  # email
            return redirect(url_for("home"))
        else:
            return "Invalid Email or Password"

    return render_template("login.html")





# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


# ---------------- HOME ----------------
@app.route("/", methods=["GET", "POST"])
def home():
    if "user" not in session:
        return redirect(url_for("login"))

    prediction = None
    if request.method == "POST":
        message = request.form["message"]

        data = vectorizer.transform([message])
        result = model.predict(data)[0]
        prediction = "SPAM" if result == 1 else "NOT SPAM"

        cursor.execute(
            "INSERT INTO messages (message, prediction) VALUES (?, ?)",
            (message, prediction)
        )
        db.commit()

    return render_template("index.html", prediction=prediction)


# ---------------- HISTORY ----------------
@app.route("/history")
def history():
    if "user" not in session:
        return redirect(url_for("login"))

    cursor.execute("SELECT message, prediction, created_at FROM messages ORDER BY id DESC")
    records = cursor.fetchall()
    return render_template("history.html", records=records)

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    # Total messages
    cursor.execute("SELECT COUNT(*) FROM messages")
    total_count = cursor.fetchone()[0]

    # Spam count
    cursor.execute("SELECT COUNT(*) FROM messages WHERE prediction='SPAM'")
    spam_count = cursor.fetchone()[0]

    # Not spam count
    cursor.execute("SELECT COUNT(*) FROM messages WHERE prediction='NOT SPAM'")
    ham_count = cursor.fetchone()[0]

    # Recent messages (last 5)
    cursor.execute("SELECT message, prediction, created_at FROM messages ORDER BY id DESC LIMIT 5")
    recent_records = cursor.fetchall()

    return render_template(
        "dashboard.html",
        total_count=total_count,
        spam_count=spam_count,
        ham_count=ham_count,
        recent_records=recent_records
    )

# ---------------- COMPOSE EMAIL ----------------
@app.route("/compose", methods=["GET", "POST"])
def compose():
    if "user" not in session:
        return redirect(url_for("login"))
    msg = None
    if request.method == "POST":
        sender = session["email"]
        receiver = request.form["receiver"]
        subject = request.form["subject"]
        body = request.form["body"]

        full_text = subject + " " + body
        data = vectorizer.transform([full_text])
        result = model.predict(data)[0]

        prediction = "SPAM" if result == 1 else "NOT SPAM"

        cursor.execute(
            "INSERT INTO emails (sender, receiver, subject, body, prediction) VALUES (?,?,?,?,?)",
            (sender, receiver, subject, body, prediction)
        )
        db.commit()

        msg = "Email sent successfully!"

    return render_template("compose.html", msg=msg)


# ---------------- INBOX ----------------
@app.route("/inbox")
def inbox():
    if "user" not in session:
        return redirect(url_for("login"))

    cursor.execute(
        "SELECT sender, subject, body, prediction, created_at \
         FROM emails WHERE receiver=? ORDER BY id DESC",
        (session["email"],)
    )

    emails = cursor.fetchall()
    return render_template("inbox.html", emails=emails)


# ---------------- SPAM FOLDER ----------------
@app.route("/spam")
def spam_folder():
    if "user" not in session:
        return redirect(url_for("login"))

    cursor.execute("""
        SELECT sender, subject, body, created_at
        FROM emails
        WHERE receiver=? AND prediction='SPAM'
        ORDER BY id DESC
    """, (session["email"],))

    emails = cursor.fetchall()

    return render_template("spam.html", emails=emails)

# ---------------- ADMIN LOGIN ----------------
from werkzeug.security import check_password_hash

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        # Get hashed password from DB
        cursor.execute("SELECT password FROM admins WHERE email=?", (email,))
        admin = cursor.fetchone()

        if admin and check_password_hash(admin[0], password):
            session["admin"] = email
            return redirect(url_for("admin_dashboard"))
        else:
            return "Invalid Admin Login"

    return render_template("admin_login.html")



# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect("/admin/login")

    # Stats
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM emails")
    email_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM emails WHERE prediction='SPAM'")
    spam_count = cursor.fetchone()[0]

    ham_count = email_count - spam_count

    spam_rate = round((spam_count / email_count) * 100, 2) if email_count > 0 else 0

    # ⭐ RECENT EMAILS (THIS WAS MISSING)
    cursor.execute("""
        SELECT sender, subject, prediction, created_at
        FROM emails
        ORDER BY id DESC
        LIMIT 5
    """)
    recent_emails = cursor.fetchall()
    return render_template(
        "admin_dashboard.html",
        user_count=user_count,
        email_count=email_count,
        spam_count=spam_count,
        ham_count=ham_count,
        spam_rate=spam_rate,
        recent_emails=recent_emails  
    )

# ---------------- ADMIN USERS ----------------
@app.route("/admin/users")
def admin_users():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    cursor.execute("SELECT id, email, status FROM users")
    users = cursor.fetchall()

    return render_template("admin_users.html", users=users)

@app.route("/admin/block/<int:user_id>")
def block_user(user_id):
    cursor.execute("UPDATE users SET status='BLOCKED' WHERE id=?", (user_id,))
    db.commit()
    return redirect("/admin/users")

@app.route("/admin/unblock/<int:user_id>")
def unblock_user(user_id):
    cursor.execute("UPDATE users SET status='ACTIVE' WHERE id=?", (user_id,))
    db.commit()
    return redirect("/admin/users")

@app.route("/admin/delete/<int:user_id>")
def delete_user(user_id):
    cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
    db.commit()
    return redirect("/admin/users")


# ---------------- ADMIN EMAILS ----------------
@app.route("/admin/emails")
def admin_emails():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    cursor.execute("SELECT sender, receiver, subject, prediction, created_at FROM emails")
    emails = cursor.fetchall()

    return render_template("admin_emails.html", emails=emails)


# ---------------- ADMIN LOGOUT ----------------
@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))


if __name__ == "__main__":
    port = int(os.version.get("PORT",5000))
    app.run(host="0.0.0.0", port=port)


