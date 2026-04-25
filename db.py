import psycopg2

conn = psycopg2.connect(
    dbname="ai_system",
    user="postgres",
    password="881233",
    host="localhost",
    port="5432"
)  

cursor = conn.cursor()