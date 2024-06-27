from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.dummy import DummyOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
from helper_functions import HelperFunctions

helper = HelperFunctions()

default_args = {
    'owner': 'airflow',
    'retries': 5,
    'retry_delay': timedelta(minutes=1)
}

dag = DAG(
    dag_id='demo_dag_for_alerting_apis_final',
    default_args=default_args,
    description='Alerting by a message to a file when a particular task state is skipped for the continuous 3 times',
    schedule_interval='*/1 * * * *',
    start_date=datetime(2024, 6, 1),
    catchup=False,
)

start = DummyOperator(task_id='start', dag=dag)
start_run = DummyOperator(task_id='start_run', dag=dag)
insert_new_record_into_audit_table = DummyOperator(task_id='insert_new_record_into_audit_table', dag=dag)
refresh_external_table = DummyOperator(task_id="refresh_external_table", dag=dag)
end = DummyOperator(task_id='end', dag=dag)

check_previous_run_status = BranchPythonOperator(
    task_id="check_previous_run_status",
    python_callable=helper.alert_notif_failure_api,
    op_kwargs={
        'dag_id': dag.dag_id,
        'task_id': 'check_previous_run_status',
        'func': helper.check_last_run_status,
        'kwargs': {
            'success_condition': 'start_run',
            'skip_condition': 'skip_run'
        }
    },
    dag=dag
)

skip_run_task = PythonOperator(
    task_id="skip_run",
    python_callable=helper.alert_notif_skipped_api,
    op_kwargs={
        'dag_id': dag.dag_id,
        'task_id': 'skip_run',
    },
    dag=dag
)

check_data_in_stream = BranchPythonOperator(
    task_id="check_data_in_stream",
    python_callable=helper.alert_notif_failure_api,
    op_kwargs={
        'dag_id': dag.dag_id,
        'task_id': 'check_data_in_stream',
        'func': helper.check_data_in_stream_v2,
        'kwargs': {
            'success_condition': 'insert_new_record_into_audit_table',
            'skip_condition': 'skipped_due_to_data_unavailability'
        }
    },
    dag=dag
)

skipped_due_to_data_unavailability = PythonOperator(
    task_id="skipped_due_to_data_unavailability",
    python_callable=helper.alert_notif_skipped_api,
    op_kwargs={
        'dag_id': dag.dag_id,
        'task_id': 'skipped_due_to_data_unavailability',
    },
    dag=dag
)

(start >> check_previous_run_status >> [skip_run_task, start_run])
(start_run >> refresh_external_table >> check_data_in_stream)
check_data_in_stream >> [skipped_due_to_data_unavailability, insert_new_record_into_audit_table]
(insert_new_record_into_audit_table >> end)
