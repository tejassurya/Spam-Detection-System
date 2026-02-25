import sqlite3
from werkzeug.security import generate_password_hash

db = sqlite3.connect("spam_detection.db")
cursor = db.cursor()

email = "admin@system.com"
password = generate_password_hash("admin123")

cursor.execute(
    "INSERT INTO admins (email, password) VALUES (?, ?)",
    (email, password)
)

db.commit()
db.close()

print("Admin created!")