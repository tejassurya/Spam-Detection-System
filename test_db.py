import mysql.connector

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="spam_detection_db",
    port=3307
)

print("Connected to XAMPP MySQL successfully!")
