import os
import logging
from datetime import datetime
from airflow.exceptions import AirflowFailException
from airflow.models import DagRun, TaskInstance
from airflow.utils.state import State
import psycopg2
import requests
from cryptography.fernet import Fernet
import json
from filekey import filekey

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class HelperFunctions:
    def __init__(self):
        self.key = filekey.encode()
        self.fernet = Fernet(self.key)
        self.postgres_conn_file_path = os.path.join(os.path.dirname(__file__), 'postgres_connection.py')
        self.airflow_api_config_file_path = os.path.join(os.path.dirname(__file__), 'airflow_api_configuration.py')
        self.alert_file_path = os.path.join(os.path.dirname(__file__), 'AlertSlack.txt')

        self.create_table_sql = self.read_sql_file("dags/config/Queries/create_skipped_data_table.sql")
        self.insert_query = self.read_sql_file("dags/config/Queries/insert_query.sql")
        self.select_query = self.read_sql_file("dags/config/Queries/select_query.sql")
        self.skip_update_query = self.read_sql_file("dags/config/Queries/skip_update_query.sql")
        self.success_update_query = self.read_sql_file("dags/config/Queries/success_update_query.sql")

    def read_sql_file(self, file_path):
        """
        from the given parameter file_path reads the data presented and return the query
        """
        try:
            with open(file_path, 'r') as file:
                queries = file.read().split(";")
                return queries[0]
        except Exception as e:
            logging.error(f"Failed to read_sql_file: {e}", exc_info=True)

    def insert_into_audit_table_for_adhoc_data(self):
        try:
            print("insert_into_audit_table_for_adhoc_data")
        except Exception as e:
            logging.error(f"Failed to insert into audit table for adhoc data: {e}", exc_info=True)

    def refresh_crm_campaign_run_external_table(self):
        try:
            print("refresh_crm_campaign_run_external_table")
        except Exception as e:
            logging.error(f"Failed to refresh CRM campaign run external table: {e}", exc_info=True)

    def decrypt_data(self, file_path):
        """
        From the file_path reads the data(encrypted) and decrypt it and change it to the json type and return it 
        """
        try:
            with open(file_path, 'rb') as file:
                encrypted_data = file.read()
            decrypted_data = self.fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data)
        except Exception as e:
            logging.error(f"Failed to decrypt data from {file_path}: {e}", exc_info=True)
            return None

    def encrypt_data(self, data, file_path):
        """
        Given data is encryped and stored it to the given file_path
        """
        try:
            encrypted_data = self.fernet.encrypt(json.dumps(data).encode())
            with open(file_path, 'wb') as encrypted_file:
                encrypted_file.write(encrypted_data)
        except Exception as e:
            logging.error(f"Failed to encrypt data to {file_path}: {e}", exc_info=True)

    def get_base_url(self):
        """
        Decrypt the data that is presented in the airflow_api_file_path and from that data genrate the base_url
        return those base_url and the decrypted_data 
        """
        try:
            airflow_api_config = self.decrypt_data(self.airflow_api_config_file_path)
            if not airflow_api_config:
                raise ValueError("Decryption of Airflow API config failed")
            base_url = f"http://{airflow_api_config['user']}:{airflow_api_config['password']}@{airflow_api_config['ip_address']}:8080/api/v1/dags"
            return base_url, airflow_api_config
        except Exception as e:
            logging.error(f"Failed to get base URL: {e}", exc_info=True)
            return None, None

    def update_database(self, dag_id, task_id, result, kwargs, conn, airflow_api_config):
        """
        Takes parameters from the alert_notif_failure function and update the database based on the result value
        """
        try:
            current_time = datetime.now()
            with conn.cursor() as cur:
                logging.info("Executing create table SQL")
                cur.execute(self.create_table_sql)
                conn.commit()

                logging.info("Checking existing record for dag_id and task_id")
                cur.execute(self.select_query, (dag_id, task_id))
                prev_count = cur.fetchone()

                if prev_count:
                    if result == kwargs['skip_condition']:
                        logging.info(f"Updating skip count for {dag_id} - {task_id}")
                        cur.execute(self.skip_update_query, (current_time, dag_id, task_id))
                        skip_count = prev_count[0] + 1

                        if skip_count >= airflow_api_config['limit']:
                            with open(self.alert_file_path, 'a') as alert_file:
                                alert_file.write(f"The DAG {dag_id} was skipped {skip_count} times continuously at {datetime.now()}\n")
                    elif result == kwargs['success_condition']:
                        logging.info(f"Updating success count for {dag_id} - {task_id}")
                        cur.execute(self.success_update_query, (current_time, dag_id, task_id))
                else:
                    logging.info(f"Inserting new record for {dag_id} - {task_id}")
                    cur.execute(self.insert_query, (dag_id, task_id, current_time))
                conn.commit()
        except Exception as e:
            logging.error(f"Failed to update database for {dag_id} - {task_id}: {e}", exc_info=True)

    def alert_notif_failure(self, dag_id, task_id, func, kwargs):
        """
        exception handling the passed function and return the result 
        if the passed func is either check_last_run_status, check_data_in_stream_v2 run the respective code 
        """
        try:
            result = func(**kwargs)

            if func in [self.check_last_run_status, self.check_data_in_stream_v2]:
                logging.info(f"Reading encrypted details from {self.postgres_conn_file_path , self.airflow_api_config_file_path}")
                postgres_conn = self.decrypt_data(self.postgres_conn_file_path)
                airflow_api_config = self.decrypt_data(self.airflow_api_config_file_path)
                logging.info(f"Decrypted postgres connection: {postgres_conn}")

                conn = psycopg2.connect(
                    user=postgres_conn["user"],
                    password=postgres_conn["password"],
                    dbname=postgres_conn["dbname"],
                    host=postgres_conn["host"],
                    port=postgres_conn["port"]
                )

                try:
                    self.update_database(dag_id, task_id, result, kwargs, conn, airflow_api_config)
                except Exception as e:
                    logging.error(f"Error interacting with the database: {e}")
                finally:
                    self.encrypt_data(postgres_conn, self.postgres_conn_file_path)
                    self.encrypt_data(airflow_api_config, self.airflow_api_config_file_path)
                    conn.close()

            return result

        except Exception as e:
            logging.error(f"Failed to run {dag_id} with task {task_id}: {e}")
            with open(self.alert_file_path, 'a') as alert_file:
                alert_file.write(f"Failed to run {dag_id} with task {task_id} at {datetime.now()}\n")
            raise

    def check_last_run_status(self, success_condition="refresh_external_table", skip_condition="skip_run"):
        """
        Based on the condition value if it is true next step else skip the current run
        """
        try:
            condition = True
            if condition:
                return success_condition
            else:
                return skip_condition
        except Exception as e:
            logging.error(f"Failed to check last run status: {e}", exc_info=True)

    def alert_notif_skipped(self, dag_id, task_id):
        """
        If that particular dag is skipped sends a alert message to the that this dag is skipped
        """
        try:
            with open(self.alert_file_path, 'a') as alert_file:
                alert_message = f"The DAG {dag_id} was skipped at {datetime.now()}\n"
                logging.info(alert_message)
                alert_file.write(alert_message)
        except Exception as e:
            logging.error(f"Failed to send alert notification for skipped DAG {dag_id}: {e}", exc_info=True)

    def check_data_in_stream_v2(self, success_condition="insert_into_audit_table", skip_condition="skipped_due_to_data_unavailability"):
        """
        Based on the condition value if it is true next step else skip the current run
        """
        try:
            condition = False
            if condition:
                return success_condition
            else:
                return skip_condition
        except Exception as e:
            logging.error(f"Failed to check data in stream: {e}", exc_info=True)

    def alert_notif_failure_api(self, dag_id, task_id, func, kwargs):
        """
        Used in the demo_dag_for_alerting_apis dag in particular 
        to execute the passed function and handle exception if any error came while runnning that 
        """
        try:
            result = func(**kwargs)
            return result
        except Exception as e:
            logging.error(f"Failed to run {dag_id} with task {task_id}: {e}")
            with open(self.alert_file_path, 'a') as alert_file:
                alert_file.write(f"Failed to run {dag_id} with task {task_id} at {datetime.now()}\n")
            raise AirflowFailException(f"The DAG {dag_id} is failed because of the TASK {task_id} is failed")

    def alert_notif_skipped_api(self, dag_id, task_id):
        """
        Used in the demo_dag_for_alerting_apis dag in particular 
        To write alert skipped message and also using the apis approach to threshold limit of skips
        """
        base_url, airflow_api_config = self.get_base_url()
        get_latest_limit_dagRuns_api = f"{base_url}/{dag_id}/dagRuns?limit={airflow_api_config['limit']}&order_by=-start_date"
        try:
            response = requests.get(get_latest_limit_dagRuns_api)
            response.raise_for_status()
            dag_runs = response.json()['dag_runs']
            run_ids = [dag_run['dag_run_id'] for dag_run in dag_runs if dag_run['state'] != 'running'][:airflow_api_config['limit']]
            logging.info(run_ids)

            states = []
            for run_id in run_ids:
                get_task_Instances_api = f"{base_url}/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}"
                response = requests.get(get_task_Instances_api)
                response.raise_for_status()
                task_instance = response.json()
                states.append(task_instance['state'])
            logging.info(states)

            self.encrypt_data(airflow_api_config, self.airflow_api_config_file_path)
            with open(self.alert_file_path, 'a') as alert_file:
                if all(state == 'success' for state in states):
                    alert_file.write(f"The DAG {dag_id} was skipped in the last 3 runs continuously at {datetime.now()}\n")
                else:
                    alert_file.write(f"The DAG {dag_id} was skipped at {datetime.now()}\n")

        except requests.exceptions.RequestException as e:
            logging.error(f"HTTP request failed: {e}")
            with open(self.alert_file_path, 'a') as alert_file:
                alert_file.write(f"Failed to check DAG {dag_id} status at {datetime.now()}: {e}\n")

    def get_all_active_dags(self):
        try:
            active_dag_ids = []
            base_url, airflow_api_config = self.get_base_url()
            api_to_get_all_active_dags = f"{base_url}?only_active=true"
            logging.info(f"Requesting {api_to_get_all_active_dags}")
            response = requests.get(api_to_get_all_active_dags)
            if response.status_code != 200:
                logging.error(f"Received status code {response.status_code} from {api_to_get_all_active_dags}")
                raise AirflowFailException(f"Failed to get active DAGs, status code: {response.status_code}")
            dags = response.json().get('dags', [])
            for dag in dags:
                active_dag_ids.append(dag['dag_id'])

            self.encrypt_data(airflow_api_config, self.airflow_api_config_file_path)
            return active_dag_ids
        except Exception as e:
            logging.error(f"Failed to get active DAGs: {e}", exc_info=True)
            raise AirflowFailException(f"Failed to get active DAGs: {e}")


    def get_all_dag_ids_last_limit_run_ids(self, active_dag_ids):
        """
        This Function takes parameter active_dag_ids which is List of dag_ids 
        and fetch the List DAG Runs API and store the respective DAG'S latest dag_run_ids in a 2D array
        """
        try:
            run_ids = []
            base_url, airflow_api_config = self.get_base_url()
            for dag_id in active_dag_ids:
                api_to_get_last_limit_run_ids_of_one_dag_id = f"{base_url}/{dag_id}/dagRuns?limit={airflow_api_config['limit']}&order_by=-start_date"
                logging.info(f"Requesting {api_to_get_last_limit_run_ids_of_one_dag_id}")
                response = requests.get(api_to_get_last_limit_run_ids_of_one_dag_id)
                if response.status_code != 200:
                    logging.error(f"Received status code {response.status_code} from {api_to_get_all_active_dags}")
                    raise AirflowFailException(f"Failed to get DAG IDs and their last limit run IDs, status code: {response.status_code}")
                dag_runs = response.json().get('dag_runs', [])
                run_ids.extend([[dag_id, dag_run['dag_run_id']] for dag_run in dag_runs])
            self.encrypt_data(airflow_api_config, self.airflow_api_config_file_path)
            return run_ids
        except Exception as e:
            logging.error(f"Failed to get DAG IDs and their last limit run IDs: {e}", exc_info=True)
            raise AirflowFailException(f"Failed to get DAG IDs and their last limit run IDs: {e}")

    def get_all_dagruns_task_instances(self, run_ids):
        """
        This Function takes parameter run_ids which is a 2D array of [dag_id, run_id]
        and fetches the List task instances API and stores the respective DAG'S number of skipped tasks
        for all run_ids in a dictionary.
        """
        try:
            states_of_all_dags_each_runs = {}
            base_url, airflow_api_config = self.get_base_url()
            for dag_id, run_id in run_ids:
                if dag_id not in states_of_all_dags_each_runs:
                    states_of_all_dags_each_runs[dag_id] = []
                api_to_get_task_instances_of_one_run_id = f"{base_url}/{dag_id}/dagRuns/{run_id}/taskInstances?limit=100"
                logging.info(f"Requesting {api_to_get_task_instances_of_one_run_id}")
                response = requests.get(api_to_get_task_instances_of_one_run_id)
                if response.status_code != 200:
                    logging.error(f"Received status code {response.status_code} from {api_to_get_all_active_dags}")
                    raise AirflowFailException(f"Failed to get task instances for all DAG runs, status code: {response.status_code}")
                task_instances = response.json().get('task_instances', [])
                skipped_count = sum(1 for task_instance in task_instances if task_instance['state'] != 'success')
                states_of_all_dags_each_runs[dag_id].append(skipped_count)
            self.encrypt_data(airflow_api_config, self.airflow_api_config_file_path)
            return states_of_all_dags_each_runs
        except Exception as e:
            logging.error(f"Failed to get task instances for all DAG runs: {e}", exc_info=True)
            raise AirflowFailException(f"Failed to get task instances for all DAG runs: {e}")


    def alert_all_continuous_skipped_dags(self, states_of_all_dags_each_runs):
        """
        This Function takes parameter states_of_all_dags_each_runs which is a dictionary with key as dag_id and value as array of no.of.skipped tasks
        if for that particular array all the values are above 2 alert it to file
        """
        try:
            with open(self.alert_file_path, 'a') as alert_file:
                for dag_id, skipped_counts in states_of_all_dags_each_runs.items():
                    if all(skipped_count > 2 for skipped_count in skipped_counts):
                        alert_message = f"The DAG {dag_id} has reached its threshold skips, please look into it\n"
                        logging.info(alert_message)
                        alert_file.write(alert_message)
        except Exception as e:
            logging.error(f"Failed to alert continuous skipped DAGs: {e}", exc_info=True)