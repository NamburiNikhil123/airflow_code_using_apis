postgres_conn = {
    "user": "airflow",
    "password": "airflow",
    "dbname": "airflow",
    "host": "172.240.2.3",
    "port" : "5432"
}


# def alert_notif_skipped_api(dag_id, task_id):
#     get_latest_3_dagRuns_api = "http://localhost:8080/api/v1/dags/{dag_id}/dagRuns?limit=3&order_by=-start_date"
#     get_task_Instances_api ="http://localhost:8080/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}"
#     #implement the functionality such that the result gotten from the above get_latest_3_dagRuns_api 
#     #store the dag_run_id of each in run_ids and iterate those run ids with get_task_Instances_api 
#     #store the "state" of all 3 apis if all 3 are  success execute below code
#     alert_file_path = os.path.join(os.path.dirname(__file__), 'CriticalAlertSlack.txt')
#                                     with open(alert_file_path, 'a') as alert_file:
#                                         alert_file.write(f"The DAG {dag_id} was skipped  3 times continuously at {datetime.now()}\n")
#     #else execute the below code
#     alert_file_path = os.path.join(os.path.dirname(__file__), 'AlertSlack.txt')
#     with open(alert_file_path, 'a') as alert_file:
#         alert_file.write(f"The DAG {dag_id} was skipped at {datetime.now()}\n")


# def alert_notif_skipped(dag_id, task_id):
#     base_url = 'http://localhost:8080/api/v1'
#     headers = {
#         'Content-Type': 'application/json',
#         'Authorization': 'Basic YOUR_AUTH_TOKEN'
#     }
    
#     try:
#         with create_session() as session:
#             dag_runs = session.query(DagRun).filter(DagRun.dag_id == dag_id).order_by(DagRun.execution_date.desc()).limit(3).all()
#             skip_count = 0

#             for dag_run in dag_runs:
#                 dag_run_id = dag_run.run_id
#                 response = requests.get(f"{base_url}/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}", headers=headers)
#                 response.raise_for_status()
#                 task_instances = response.json()
                
#                 if all(task_instance['state'] == 'skipped' for task_instance in task_instances['task_instances']):
#                     skip_count += 1
            
#             if skip_count == 3:
#                 critical_alert_file_path = os.path.join(os.path.dirname(__file__), 'CriticalAlertSlack.txt')
#                 with open(critical_alert_file_path, 'a') as alert_file:
#                     alert_file.write(f"The DAG {dag_id} was skipped continuously 3 times at {datetime.now()}\n")
#             else:
#                 alert_file_path = os.path.join(os.path.dirname(__file__), 'AlertSlack.txt')
#                 with open(alert_file_path, 'a') as alert_file:
#                     alert_file.write(f"The DAG {dag_id} was skipped at {datetime.now()}\n")
    
#     except Exception as e:
#         logging.error(f"Failed to check skipped status for {dag_id} with task {task_id}: {e}")
#         alert_file_path = os.path.join(os.path.dirname(__file__), 'AlertSlack.txt')
#         with open(alert_file_path, 'a') as alert_file:
#             alert_file.write(f"Error while checking skipped status for {dag_id} with task {task_id} at {datetime.now()}: {e}\n")


# def alert_notif_failure(dag_id, task_id, func, kwargs):
#     try:
#         result = func(**kwargs)
#         print("Type of result is ",type(result))
#         current_time = datetime.now()
        
#         if func in [check_last_run_status, check_data_in_stream_v2]:
#             conn = psycopg2.connect(
#                 user=postgres_conn["user"],
#                 password=postgres_conn["password"],
#                 dbname=postgres_conn["dbname"],
#                 host=postgres_conn["host"],
#                 port=postgres_conn["port"]
#             )
#             create_table_sql = """
#             CREATE TABLE IF NOT EXISTS skipped_data (
#               id SERIAL PRIMARY KEY,
#               dag_id VARCHAR(255) NOT NULL,
#               task_id VARCHAR(255) NOT NULL,
#               continous_skip_count INT NOT NULL, 
#               datetime TIMESTAMP without TIME zone NOT NULL
#             );
#             """
#             select_query = """
#             SELECT continous_skip_count FROM skipped_data WHERE dag_id=%s AND task_id=%s
#             """
#             insert_query = """
#             INSERT INTO skipped_data (dag_id, task_id, continous_skip_count, datetime) VALUES (%s, %s, 1, %s)
#             """
#             skip_update_query = """
#             UPDATE skipped_data SET continous_skip_count = continous_skip_count + 1, datetime = %s WHERE dag_id = %s AND task_id = %s
#             """
#             success_update_query = """
#             UPDATE skipped_data SET continous_skip_count = 0, datetime = %s WHERE dag_id = %s AND task_id = %s
#             """
            

#             try:
#                 with conn:
#                     with conn.cursor() as cur:
#                         # Create the table if it doesn't exist
#                         cur.execute(create_table_sql)
#                         conn.commit()

#                         # Check if there's an existing record for the given dag_id and task_id
#                         cur.execute(select_query, (dag_id, task_id))
#                         row = cur.fetchone()
#                         if row:
#                             if result == 'skip_run':
#                                 cur.execute(skip_update_query, (current_time, dag_id, task_id))
#                                 if(row[0] >= 3):
#                                 alert_file_path = os.path.join(os.path.dirname(__file__), 'AlertSlack.txt')
#                                     with open(alert_file_path, 'a') as alert_file:
#                                         alert_file.write(f"The DAG {dag_id} was skipped at {datetime.now()}\n")    
#                             elif result == 'start_run':
#                                 cur.execute(success_update_query, (current_time, dag_id, task_id))
#                         else:
#                             cur.execute(insert_query, (dag_id, task_id, current_time))
#                         conn.commit()
#             except Exception as e:
#                 logging.error(f"Error interacting with the database: {e}")
#             finally:
#                 conn.close()
        
#         return result
#     except Exception as e:
#         logging.error(f"Failed to run {dag_id} with task {task_id}: {e}")

#         alert_file_path = os.path.join(os.path.dirname(__file__), 'AlertSlack.txt')
#         with open(alert_file_path, 'a') as alert_file:
#             alert_file.write(f"Failed to run {dag_id} with task {task_id} at {datetime.now()}\n")
        
#         return 'start_run'