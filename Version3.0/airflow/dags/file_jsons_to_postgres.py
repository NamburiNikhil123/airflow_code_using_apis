# import logging
# from airflow import DAG
# from airflow.operators.python import PythonOperator
# from datetime import datetime, timedelta
# import json
# import re
# import psycopg2
# import requests
# from requests.auth import HTTPBasicAuth


# # Define the default arguments
# default_args = {
#     'owner': 'airflow',
#     'retries': 5,
#     'retry_delay': timedelta(minutes=1)
# }

# # Initialize the DAG
# dag = DAG(
#     dag_id='file_jsons_to_postgres',
#     default_args=default_args,
#     description='Process JSON data from a file and insert valid entries to PostgreSQL',
#     schedule_interval='*/5 * * * *',
#     start_date=datetime(2024, 6, 1),
#     catchup=False,
# )

# def read_data_from_file(**kwargs):
#     with open("dags/dataForAirflow.txt", "r") as f:
#         json_data = f.read()
#     data = json.loads(json_data)
#     logging.info(f"Loaded JSON data: {data}")
#     kwargs['ti'].xcom_push(key='json_data', value=data)

# def is_valid_date(date_str, date_formats=None):
#     if not date_formats:
#         date_formats = [
#             '%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y', '%m.%d.%Y',
#             '%Y/%m/%d', '%Y-%d-%m', '%Y.%m.%d', '%d-%m-%Y',
#             '%d.%m.%Y', '%d/%m/%Y', '%m-%d-%y', '%m/%d/%y',
#             '%d-%m-%y', '%d.%m.%y', '%d/%m/%y', '%m.%d.%y'
#         ]

#     for date_format in date_formats:
#         try:
#             date_obj = datetime.strptime(date_str, date_format)
#             logging.info(f"Successfully parsed date {date_str} using format {date_format}")
#             return date_obj.strftime('%Y-%m-%d')
#         except ValueError:
#             continue
#     logging.warning(f"Failed to parse date {date_str} with available formats")
#     return None

# regex = r'\b[A-Za-z0-9!#$%^&*.]+@[a-z]{1,9}+\.[a-z]{2,3}\b'

# def filter_data(**kwargs):
#     ti = kwargs['ti']
#     data = ti.xcom_pull(key='json_data', task_ids='read_file')
#     if not data:
#         logging.error("No data fetched from XCom")
#         return
#     valid_data = []
#     for entry in data:
#         if 'name' in entry and len(entry['name']) > 3 and 'email' in entry and re.fullmatch(regex, entry['email']):
#             valid_date = is_valid_date(entry['date'])
#             if valid_date:
#                 entry['date'] = valid_date
#                 valid_data.append(entry)
#     logging.info(f"Filtered valid data: {valid_data}")
#     ti.xcom_push(key='valid_data', value=valid_data)

# def create_table():
#     conn = psycopg2.connect(
#         user=postgres_conn["user"],
#         password=postgres_conn["password"],
#         dbname=postgres_conn["dbname"],
#         host=postgres_conn["host"],
#         port=postgres_conn["port"]
#     )
#     create_table_sql = """
#     CREATE TABLE IF NOT EXISTS valid_data (
#         id SERIAL PRIMARY KEY,
#         name VARCHAR(255) NOT NULL,
#         email VARCHAR(255) NOT NULL,
#         date DATE NOT NULL
#     );
#     """
#     try:
#         with conn:
#             with conn.cursor() as cur:
#                 cur.execute(create_table_sql)
#                 conn.commit()
#     except Exception as e:
#         logging.error(f"Error creating table: {e}")
#     finally:
#         conn.close()

# def insert_json(**kwargs):
#     ti = kwargs['ti']
#     valid_data = ti.xcom_pull(key='valid_data', task_ids='filter_data')
#     if valid_data:
#         conn = psycopg2.connect(
#            user=postgres_conn["user"],
#            password=postgres_conn["password"],
#            dbname=postgres_conn["dbname"],
#            host=postgres_conn["host"],
#            port=postgres_conn["port"]
#         )
#         insert_query = """
#         INSERT INTO valid_data (name, email, date) VALUES (%s, %s, %s)
#         """
#         try:
#             with conn:
#                 with conn.cursor() as cur:
#                     for entry in valid_data:
#                         logging.info(f"Inserting entry: {entry}")
#                         try:
#                             cur.execute(insert_query, (entry['name'], entry['email'], entry['date']))
#                             conn.commit()
#                         except Exception as e:
#                             logging.error(f"Error inserting entry: {entry}, Error: {e}")
#             logging.info("Data insertion completed successfully.")
#         except Exception as e:
#             logging.error(f"Error inserting data: {e}")
#         finally:
#             conn.close()
#     else:
#         logging.info("No valid data to insert.")


# # def get_dag_run_ids(**context):
# #     dag_id = context['dag'].dag_id
# #     # Replace with your database connection URI
# #     DATABASE_URI = 'sqlite:////path/to/airflow/airflow.db'  # Change to your actual database URI
# #     engine = create_engine(DATABASE_URI)
# #     connection = engine.connect()
# #     metadata = MetaData(bind=engine)

# #     # Reflect the 'dag_run' table from the database
# #     dag_run_table = Table('dag_run', metadata, autoload_with=engine)

# #     # Query the table to get the last 3 run IDs for the specified DAG
# #     query = select([dag_run_table.c.dag_run_id]).where(dag_run_table.c.dag_id == dag_id).order_by(desc(dag_run_table.c.execution_date)).limit(3)
# #     result = connection.execute(query)

# #     # Fetch the run IDs
# #     run_ids = [row['dag_run_id'] for row in result]
# #     print(f"Last 3 run IDs: {run_ids}")

# #     return run_ids



# # # Function to get task instances
# # def get_task_instances(**kwargs):
# #     endpoint = f'{task_status["airflow_base_url"]}/api/v1/dags/{task_status["dag_id"]}/tasks/{task_status["task_id"]}'
# #     try:
# #         logging.info(f"Attempting to fetch task instances from: {endpoint}")
# #         response = requests.get(endpoint, auth=HTTPBasicAuth(task_status["user"], task_status["password"]))
# #         response.raise_for_status()
# #         task_instances = response.json()
# #         logging.info(f"Fetched task instances: {task_instances}")
# #         return task_instances
# #     except requests.exceptions.RequestException as e:
# #         logging.error(f"Request failed: {e}")
# #         return None


# read_data_from_file_task = PythonOperator(
#     task_id='read_file',
#     python_callable=read_data_from_file,
#     dag=dag
# )

# filter_data_task = PythonOperator(
#     task_id='filter_data',
#     python_callable=filter_data,
#     dag=dag
# )

# create_table_task = PythonOperator(
#     task_id='create_table',
#     python_callable=create_table,
#     dag=dag
# )

# insert_json_task = PythonOperator(
#     task_id='insert_json',
#     python_callable=insert_json,
#     dag=dag
# )

# # # Define the task using PythonOperator
# # get_run_ids_task = PythonOperator(
# #     task_id='get_run_ids',
# #     provide_context=True,
# #     python_callable=get_dag_run_ids,
# #     dag=dag,
# # )

# # get_task_instances_task = PythonOperator(
# #     task_id='get_task_instances',
# #     python_callable=get_task_instances,
# #     dag=dag
# # )

# # Set the task dependencies
# read_data_from_file_task >> filter_data_task >> create_table_task >> insert_json_task