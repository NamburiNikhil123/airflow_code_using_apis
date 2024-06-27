# from airflow import DAG
# from airflow.operators.python_operator import PythonOperator
# from airflow.hooks.postgres_hook import PostgresHook
# from datetime import datetime, timedelta

# # Function to create the table
# def create_table():
#     postgres_hook = PostgresHook(postgres_conn_id='postgres_conn')
#     create_table_sql = """
#     CREATE TABLE IF NOT EXISTS valid_data2 (
#         id SERIAL PRIMARY KEY,
#         name VARCHAR(255) NOT NULL,
#         email VARCHAR(255) NOT NULL,
#         date TIMESTAMP NOT NULL
#     );
#     """
#     postgres_hook.run(create_table_sql)

# # Default arguments for the DAG
# default_args = {
#     'owner': 'airflow',
#     'retries': 5,
#     'retry_delay': timedelta(minutes=1),
# }

# # Define the DAG
# with DAG(
#     'create_table',
#     default_args=default_args,
#     description='A simple DAG to create a PostgreSQL table',
#     schedule_interval=timedelta(days=1),
#     start_date=datetime(2024, 6, 1),
#     catchup=False,
# ) as dag:

#     create_table_task = PythonOperator(
#         task_id='create_table',
#         python_callable=create_table,
#     )

#     create_table_task
