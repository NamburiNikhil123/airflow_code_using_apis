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
import traceback

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
        Reads SQL queries from the specified file_path and returns the first query found.
        
        Args:
            file_path (str): Path to the SQL file.
            
        Returns:
            str: First SQL query found in the file.
        """
        try:
            with open(file_path, 'r') as file:
                queries = file.read().split(";")
                return queries[0]
        except Exception as e:
            logging.error(f"Failed to read_sql_file: {e}")
            logging.error(traceback.format_exc())

    def insert_into_audit_table_for_adhoc_data(self):
        """
        Placeholder function to insert adhoc data into an audit table.
        """
        try:
            print("insert_into_audit_table_for_adhoc_data")
        except Exception as e:
            logging.error(f"Failed to insert into audit table for adhoc data: {e}")
            logging.error(traceback.format_exc())

    def refresh_crm_campaign_run_external_table(self):
        """
        Placeholder function to refresh an external CRM campaign run table.
        """
        try:
            print("refresh_crm_campaign_run_external_table")
        except Exception as e:
            logging.error(f"Failed to refresh CRM campaign run external table: {e}")
            logging.error(traceback.format_exc())

    def decrypt_data(self, file_path):
        """
        Decrypts data from the specified file_path, assumed to be encrypted JSON.
        
        Args:
            file_path (str): Path to the encrypted data file.
            
        Returns:
            dict: Decrypted JSON data.
        """
        try:
            with open(file_path, 'rb') as file:
                encrypted_data = file.read()
            decrypted_data = self.fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data)
        except Exception as e:
            logging.error(f"Failed to decrypt data from {file_path}: {e}")
            logging.error(traceback.format_exc())
            return None

    def encrypt_data(self, data, file_path):
        """
        Encrypts the given data and writes it to the specified file_path.
        
        Args:
            data (dict): Data to be encrypted (should be JSON serializable).
            file_path (str): Path to write the encrypted data.
        """
        try:
            encrypted_data = self.fernet.encrypt(json.dumps(data).encode())
            with open(file_path, 'wb') as encrypted_file:
                encrypted_file.write(encrypted_data)
        except Exception as e:
            logging.error(f"Failed to encrypt data to {file_path}: {e}")
            logging.error(traceback.format_exc())

    def get_base_url(self):
        """
        Retrieves and generates a base URL using decrypted Airflow API configuration.
        
        Returns:
            tuple: Tuple containing base_url (str) and decrypted_data (dict).
                If decryption fails, returns (None, None).
        """
        try:
            airflow_api_config = self.decrypt_data(self.airflow_api_config_file_path)
            if not airflow_api_config:
                raise ValueError("Decryption of Airflow API config failed")
            base_url = f"http://{airflow_api_config['user']}:{airflow_api_config['password']}@{airflow_api_config['ip_address']}:8080/api/v1/dags"
            return base_url, airflow_api_config
        except Exception as e:
            logging.error(f"Failed to get base URL: {e}")
            logging.error(traceback.format_exc())
            return None, None

    def update_database(self, dag_id, task_id, result, kwargs, conn, airflow_api_config):
        """
        Updates the database based on the result value from a function call.

        Args:
            dag_id (str): The DAG ID associated with the task.
            task_id (str): The task ID within the DAG.
            result: The result obtained from the function call.
            kwargs (dict): Additional keyword arguments passed to the function.
            conn: psycopg2 database connection object.
            airflow_api_config (dict): Decrypted Airflow API configuration.

        Raises:
            Exception: If an error occurs during database update.

        Notes:
            - Uses self.create_table_sql, self.select_query, self.skip_update_query,
            self.success_update_query, and self.insert_query attributes.
            - Logs operations using logging.info().
            - Writes alerts to self.alert_file_path when necessary.
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
            logging.error(f"Failed to update database for {dag_id} - {task_id}: {e}")
            logging.error(traceback.format_exc())

    def alert_notif_failure(self, dag_id, task_id, func, kwargs):
        """
        Executes a function specified by func with arguments in kwargs and handles failures.

        Args:
            dag_id (str): The DAG ID associated with the task.
            task_id (str): The task ID within the DAG.
            func (function): The function to execute.
            kwargs (dict): Arguments to pass to the function.

        Returns:
            The result obtained from the function call.

        Raises:
            AirflowFailException: If the function execution fails.

        Notes:
            - Logs operations using logging.info() and logging.error().
            - Decrypts data from self.postgres_conn_file_path and self.airflow_api_config_file_path.
            - Updates database using self.update_database() method.
            - Encrypts data back after usage.
            - Writes alerts to self.alert_file_path when necessary.
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
            raise AirflowFailException(f"Failed to run {dag_id} with task {task_id}: {e}")

    def check_last_run_status(self, success_condition="refresh_external_table", skip_condition="skip_run"):
        """
        Checks the last run status and returns a condition based on success or skip.

        Args:
            success_condition (str): Condition to return if successful.
            skip_condition (str): Condition to return if skipped.

        Returns:
            str: Either success_condition or skip_condition based on the check.

        Raises:
            Exception: If an error occurs during status check.

        Notes:
            - Logs operations using logging.error().
        """
        try:
            condition = False
            if condition:
                return success_condition
            else:
                return skip_condition
        except Exception as e:
            logging.error(f"Failed to check last run status: {e}")
            logging.error(traceback.format_exc())

    def alert_notif_skipped(self, dag_id, task_id):
        """
        Sends an alert notification when a DAG task is skipped.

        Args:
            dag_id (str): The DAG ID associated with the skipped task.
            task_id (str): The task ID within the DAG.

        Raises:
            Exception: If an error occurs while sending the alert notification.

        Notes:
            - Logs operations using logging.info() and logging.error().
            - Writes alerts to self.alert_file_path.
        """
        try:
            with open(self.alert_file_path, 'a') as alert_file:
                alert_message = f"The DAG {dag_id} was skipped at {datetime.now()}\n"
                logging.info(alert_message)
                alert_file.write(alert_message)
        except Exception as e:
            logging.error(f"Failed to send alert notification for skipped DAG {dag_id}: {e}")
            logging.error(traceback.format_exc())

    def check_data_in_stream_v2(self, success_condition="insert_into_audit_table", skip_condition="skipped_due_to_data_unavailability"):
        """
        Checks data in stream and returns a condition based on success or skip.

        Args:
            success_condition (str): Condition to return if successful.
            skip_condition (str): Condition to return if skipped.

        Returns:
            str: Either success_condition or skip_condition based on the check.

        Raises:
            Exception: If an error occurs during data stream check.

        Notes:
            - Logs operations using logging.error().
        """
        try:
            condition = True
            if condition:
                return success_condition
            else:
                return skip_condition
        except Exception as e:
            logging.error(f"Failed to check data in stream: {e}")
            logging.error(traceback.format_exc())

    def alert_notif_failure_api(self, dag_id, task_id, func, kwargs):
        """
        Executes a function specified by func with arguments in kwargs and handles failures.

        Args:
            dag_id (str): The DAG ID associated with the task.
            task_id (str): The task ID within the DAG.
            func (function): The function to execute.
            kwargs (dict): Arguments to pass to the function.

        Returns:
            The result obtained from the function call.

        Raises:
            AirflowFailException: If the function execution fails.

        Notes:
            - Logs operations using logging.info() and logging.error().
            - Writes alerts to self.alert_file_path when necessary.
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
        Sends alert notifications for skipped DAGs using Airflow API approach.

        Args:
            dag_id (str): The DAG ID associated with the skipped task.
            task_id (str): The task ID within the DAG.

        Raises:
            AirflowFailException: If an error occurs during API requests or alert writing.

        Notes:
            - Uses self.get_base_url(), self.decrypt_data(), self.encrypt_data() methods.
            - Logs operations using logging.info() and logging.error().
            - Writes alerts to self.alert_file_path.
        """
        try:
            base_url, airflow_api_config = self.get_base_url()
            get_latest_limit_dagRuns_api = f"{base_url}/{dag_id}/dagRuns?limit={airflow_api_config['limit']}&order_by=-start_date"
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
            logging.error(traceback.format_exc())
            with open(self.alert_file_path, 'a') as alert_file:
                alert_file.write(f"Failed to check DAG {dag_id} status at {datetime.now()}: {e}\n")

    def get_all_active_dags(self):
        """
        Retrieves all active DAG IDs using Airflow List DAGs API.

        Returns:
            list: List of active DAG IDs.

        Raises:
            AirflowFailException: If an error occurs during API request or response handling.

        Notes:
            - Uses self.get_base_url(), self.decrypt_data(), and self.encrypt_data() methods.
            - Logs operations using logging.info() and logging.error().
        """
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
            logging.error(f"Failed to get active DAGs: {e}")
            logging.error(traceback.format_exc())
            raise AirflowFailException(f"Failed to get active DAGs: {e}")


    def get_all_dag_ids_last_limit_run_ids(self, active_dag_ids):
        """
        Retrieves the last limit run IDs for each DAG in the active_dag_ids list using Airflow List DAG Runs API.

        Args:
            active_dag_ids (list): List of active DAG IDs.

        Returns:
            list: List of [dag_id, run_id] pairs representing the latest run IDs for each DAG.

        Raises:
            AirflowFailException: If an error occurs during API request or response handling.

        Notes:
            - Uses self.get_base_url(), self.decrypt_data(), and self.encrypt_data() methods.
            - Logs operations using logging.info() and logging.error().
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
            logging.error(f"Failed to get DAG IDs and their last limit run IDs: {e}")
            logging.error(traceback.format_exc())
            raise AirflowFailException(f"Failed to get DAG IDs and their last limit run IDs: {e}")

    def get_all_dagruns_task_instances(self, run_ids):
        """
        Retrieves task instances for all run IDs in the run_ids list using Airflow List Task Instances API.

        Args:
            run_ids (list): List of [dag_id, run_id] pairs representing the run IDs.

        Returns:
            dict: Dictionary where keys are dag_id and values are counts of skipped tasks across runs.

        Raises:
            AirflowFailException: If an error occurs during API request or response handling.

        Notes:
            - Uses self.get_base_url(), self.decrypt_data(), and self.encrypt_data() methods.
            - Logs operations using logging.info() and logging.error().
        """
        try:
            states_of_all_dags_each_runs = {}
            base_url, airflow_api_config = self.get_base_url()
            for dag_id, run_id in run_ids:
                api_to_get_task_instances_of_one_run_id = f"{base_url}/{dag_id}/dagRuns/{run_id}/taskInstances/end"
                logging.info(f"Requesting {api_to_get_task_instances_of_one_run_id}")
                response = requests.get(api_to_get_task_instances_of_one_run_id)
                if response.status_code != 200:
                    logging.error(f"Received status code {response.status_code} from {api_to_get_task_instances_of_one_run_id}")
                    raise AirflowFailException(f"Failed to get task instances, status code: {response.status_code}")

                task_instance = response.json()
                if task_instance['state'] != 'success':
                    if dag_id not in states_of_all_dags_each_runs:
                        states_of_all_dags_each_runs[dag_id] = 0
                    states_of_all_dags_each_runs[dag_id] += 1

            self.encrypt_data(airflow_api_config, self.airflow_api_config_file_path)
            return states_of_all_dags_each_runs
        except Exception as e:
            logging.error(f"Failed to get task instances for all DAG runs: {e}")
            logging.error(traceback.format_exc())
            raise AirflowFailException(f"Failed to get task instances for all DAG runs: {e}")

    def alert_all_continuous_skipped_dags(self, states_of_all_dags_each_runs):
        """
        Alerts continuous skipped DAGs based on the states_of_all_dags_each_runs dictionary.

        Args:
            states_of_all_dags_each_runs (dict): Dictionary where keys are dag_id and values are counts of skipped tasks.

        Raises:
            AirflowFailException: If an error occurs during alert writing or encryption.

        Notes:
            - Uses self.get_base_url(), self.encrypt_data(), and self.alert_file_path.
            - Logs operations using logging.info() and logging.error().
        """
        try:
            base_url, airflow_api_config = self.get_base_url()
            with open(self.alert_file_path, 'a') as alert_file:
                for dag_id, count_of_not_success_of_end_task in states_of_all_dags_each_runs.items():
                    if count_of_not_success_of_end_task >= airflow_api_config['limit']:
                        alert_message = f"The DAG {dag_id} has reached its threshold skips, please look into it\n"
                        logging.info(alert_message)
                        alert_file.write(alert_message)
            self.encrypt_data(airflow_api_config, self.airflow_api_config_file_path)
        except Exception as e:
            logging.error(f"Failed to alert continuous skipped DAGs: {e}")
            logging.error(traceback.format_exc())