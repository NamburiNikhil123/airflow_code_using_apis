import os
import logging
from datetime import datetime
from airflow.exceptions import AirflowSkipException
from airflow.models import DagRun, TaskInstance
from airflow.utils.session import create_session
import psycopg2
from config.postgres_conn import postgres_conn
import requests
from config.airflow_api_config import airflow_api_config

# base URL for the Airflow APIs globally declared and the API config is coming from the config folder  
base_url = f"http://{airflow_api_config['user']}:{airflow_api_config['password']}@{airflow_api_config['ip_address']}:8080/api/v1/dags"

def insert_into_audit_table_for_adhoc_data():
    print("insert_into_audit_table_for_adhoc_data")

def refresh_crm_campaign_run_external_table():
    print("refresh_crm_campaign_run_external_table")

#It will execute the whatever function is passed to it and Throw exception if any error came
def alert_notif_failure(dag_id, task_id, func, kwargs):
    try:
        result = func(**kwargs)
        current_time = datetime.now()
        if func in [check_last_run_status, check_data_in_stream_v2]:
            conn = psycopg2.connect(
                user=postgres_conn["user"],
                password=postgres_conn["password"],
                dbname=postgres_conn["dbname"],
                host=postgres_conn["host"],
                port=postgres_conn["port"]
            )
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS skipped_data (
              id SERIAL PRIMARY KEY,
              dag_id VARCHAR(255) NOT NULL,
              task_id VARCHAR(255) NOT NULL,
              continous_skip_count INT NOT NULL, 
              datetime TIMESTAMP without TIME zone NOT NULL
            );
            """
            select_query = """
            SELECT continous_skip_count FROM skipped_data WHERE dag_id=%s AND task_id=%s
            """
            insert_query = """
            INSERT INTO skipped_data (dag_id, task_id, continous_skip_count, datetime) VALUES (%s, %s, 0, %s)
            """
            skip_update_query = """
            UPDATE skipped_data SET continous_skip_count = continous_skip_count + 1, datetime = %s WHERE dag_id = %s AND task_id = %s
            """
            success_update_query = """
            UPDATE skipped_data SET continous_skip_count = 0, datetime = %s WHERE dag_id = %s AND task_id = %s
            """
            
            try:
                with conn:
                    with conn.cursor() as cur:
                        # Create the table if it doesn't exist
                        cur.execute(create_table_sql)
                        conn.commit()

                        # Check if there's an existing record for the given dag_id and task_id
                        cur.execute(select_query, (dag_id, task_id))
                        #get the previous count of skipped store it to below variable 
                        prev_count = cur.fetchone()
                        if prev_count:
                            #if this running dag state is skipped increase the count if the threshold is reached do alerting
                            if result == kwargs['skip_condition']:
                                cur.execute(skip_update_query, (current_time, dag_id, task_id))
                                skip_count = prev_count[0]+1
                                if skip_count >= airflow_api_config['limit']:
                                    alert_file_path = os.path.join(os.path.dirname(__file__), 'CriticalAlertSlack.txt')
                                    with open(alert_file_path, 'a') as alert_file:
                                        alert_file.write(f"The DAG {dag_id} was skipped  {skip_count} times continuously at {datetime.now()}\n")    
                            #if this running dag state is success make the count to zero
                            elif result == kwargs['success_condition']:
                                cur.execute(success_update_query, (current_time, dag_id, task_id))
                        else:
                            #if no result after select query insert the row with count 0
                            cur.execute(insert_query, (dag_id, task_id, current_time))
                        
                        conn.commit()
            except Exception as e:
                logging.error(f"Error interacting with the database: {e}")
            finally:
                conn.close()
        return result
    except Exception as e:
        logging.error(f"Failed to run {dag_id} with task {task_id}: {e}")
        #If any errors arise alert that to a file
        alert_file_path = os.path.join(os.path.dirname(__file__), 'AlertSlack.txt')
        with open(alert_file_path, 'a') as alert_file:
            alert_file.write(f"Failed to run {dag_id} with task {task_id} at {datetime.now()}\n")
        
#Based on the condition value if it is true next step else skip the current run
def check_last_run_status(success_condition="refresh_external_table", skip_condition="skip_run"):
    condition = False
    if condition:
        return success_condition
    else:
        return skip_condition
#If that particular dag is skipped sends a alert message to the that this dag is skipped
def alert_notif_skipped(dag_id, task_id):
    alert_file_path = os.path.join(os.path.dirname(__file__), 'AlertSlack.txt')
    with open(alert_file_path, 'a') as alert_file:
        alert_file.write(f"The DAG {dag_id} was skipped at {datetime.now()}\n")
#Based on the condition value if it is true next step else skip the current run
def check_data_in_stream_v2(success_condition="insert_into_audit_table", skip_condition="skipped_due_to_data_unavailability"):
    condition = True
    if condition:
        return success_condition
    else:
        return skip_condition
#Used in the demo_dag_for_alerting_apis dag in particular to execute the passed function and handle exception if any error came while runnning that 
def alert_notif_failure_api(dag_id, task_id, func, kwargs):
    try:
        result = func(**kwargs)
        return result
    except Exception as e:
        logging.error(f"Failed to run {dag_id} with task {task_id}: {e}")
        alert_file_path = os.path.join(os.path.dirname(__file__), 'AlertSlack.txt')
        with open(alert_file_path, 'a') as alert_file:
            alert_file.write(f"Failed to run {dag_id} with task {task_id} at {datetime.now()}\n")
#Used in the demo_dag_for_alerting_apis dag in particular to write alert skipped message and also using the apis approach to threshold limit of skips
def alert_notif_skipped_api(dag_id, task_id):
    get_latest_limit_dagRuns_api = f"{base_url}/{dag_id}/dagRuns?limit={airflow_api_config['limit']}&order_by=-start_date"
    
    try:
        #Get the latest 3 DAG runs
        response = requests.get(get_latest_limit_dagRuns_api)
        response.raise_for_status()
        dag_runs = response.json()['dag_runs']
        # Exclude the current running instance and check get the dag_run_ids and store it
        run_ids = [dag_run['dag_run_id'] for dag_run in dag_runs if dag_run['state'] != 'running'][:airflow_api_config['limit']]
        logging.info(run_ids)

        #Check the state of the task instances for the latest 3 DAG runs
        states = []
        for run_id in run_ids:
            get_task_Instances_api = f"{base_url}/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}"
            response = requests.get(get_task_Instances_api)
            response.raise_for_status()
            task_instance = response.json()
            states.append(task_instance['state'])
        logging.info(states)

        #Log alerts based on the state of the task instances
        if all(state == 'success' for state in states):
            alert_file_path = os.path.join(os.path.dirname(__file__), 'CriticalAlertSlack.txt')
            with open(alert_file_path, 'a') as alert_file:
                alert_file.write(f"The DAG {dag_id} was skipped 3 times continuously at {datetime.now()}\n")
        else:
            alert_file_path = os.path.join(os.path.dirname(__file__), 'AlertSlack.txt')
            with open(alert_file_path, 'a') as alert_file:
                alert_file.write(f"The DAG {dag_id} was skipped at {datetime.now()}\n")

    except requests.exceptions.RequestException as e:
        logging.error(f"HTTP request failed: {e}")
        alert_file_path = os.path.join(os.path.dirname(__file__), 'AlertSlack.txt')
        with open(alert_file_path, 'a') as alert_file:
            alert_file.write(f"Failed to check DAG {dag_id} status at {datetime.now()}: {e}\n")

#funtion is get all active dags through List DAGs API
def get_all_active_dags():
    active_dag_ids = []
    api_to_get_all_active_dags = f"{base_url}?only_active=true"
    logging.info(f"Requesting {api_to_get_all_active_dags}")
    response = requests.get(api_to_get_all_active_dags)
    response.raise_for_status()
    dags = response.json().get('dags', [])
    for dag in dags:
        active_dag_ids.append(dag['dag_id'])
    logging.info(f"Active DAGs: {active_dag_ids}")
    return active_dag_ids

#funtion to get if all the running dags and storing it is a dictnory with dag_id as key and value are array of run_ids
def get_all_dag_ids_last_limit_run_ids(active_dag_ids):
    run_ids = {}
    for dag_id in active_dag_ids:
        api_to_get_last_limit_run_ids_of_one_dag_id = f"{base_url}/{dag_id}/dagRuns?limit={airflow_api_config['limit']}&order_by=-start_date"
        logging.info(f"Requesting {api_to_get_last_limit_run_ids_of_one_dag_id}")
        response = requests.get(api_to_get_last_limit_run_ids_of_one_dag_id)
        response.raise_for_status()
        dag_runs = response.json().get('dag_runs', [])
        
        run_ids[dag_id] = [dag_run['dag_run_id'] for dag_run in dag_runs]
    
    logging.info(f"Run IDs: {run_ids}")
    return run_ids
#function to get the task instances of all the run_ids and storing it in a dictnory with key as dag_id and value as array numbers which are count of skipped tasks in that run
def get_all_dagruns_task_instances(run_ids):
    states_of_all_dags_each_runs = {}
    for dag_id, dag_run_ids in run_ids.items():
        states_of_all_dags_each_runs[dag_id] = []
        for run_id in dag_run_ids:
            api_to_get_task_instances_of_one_run_id = f"{base_url}/{dag_id}/dagRuns/{run_id}/taskInstances?limit=100"
            logging.info(f"Requesting {api_to_get_task_instances_of_one_run_id}")
            response = requests.get(api_to_get_task_instances_of_one_run_id)
            response.raise_for_status()
            task_instances = response.json().get('task_instances', [])
            
            skipped_count = sum(1 for task_instance in task_instances if task_instance['state'] == 'skipped')
            states_of_all_dags_each_runs[dag_id].append(skipped_count)
    
    logging.info(f"States of all DAGs' runs: {states_of_all_dags_each_runs}")
    return states_of_all_dags_each_runs
#if the skip cou nt is greater than 2 in all the run_ids send an alert
def alert_all_continuous_skipped_dags(states_of_all_dags_each_runs):
    alert_file_path = os.path.join(os.path.dirname(__file__), 'CriticalAlertSlack.txt')
    with open(alert_file_path, 'a') as alert_file:
        for dag_id, skipped_counts in states_of_all_dags_each_runs.items():
            if all(skipped_count > 2 for skipped_count in skipped_counts):
                alert_message = f"The DAG {dag_id} was reach its threshold skips please look into it\n"
                logging.info(alert_message)
                alert_file.write(alert_message)

