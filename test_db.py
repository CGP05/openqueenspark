import os
import sqlite3

os.chdir(r"c:\Users\Christian\Documents\learning programming\openqueenspark")

from src.database import create_tables

# Initialize tables
create_tables()
print("Tables created successfully!")

# Verify
conn = sqlite3.connect("database.db")
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables in database:", [t[0] for t in tables])
conn.close()
