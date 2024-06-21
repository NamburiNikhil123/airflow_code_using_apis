from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.dummy import DummyOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import logging
from helper_functions import alert_notif_failure, check_last_run_status, alert_notif_skipped, check_data_in_stream_v2, insert_into_audit_table_for_adhoc_data, refresh_crm_campaign_run_external_table

default_args = {
    'owner': 'airflow',
    'retries': 5,
    'retry_delay': timedelta(minutes=1)
}

dag = DAG(
    dag_id='demo_dag_for_alerting_final_1',
    default_args=default_args,
    description='Alerting by a message to a file when a particular task state is skipped for the continuous 3 times',
    schedule_interval='*/1 * * * *',
    start_date=datetime(2024, 6, 1),
    catchup=False,
)

start = DummyOperator(task_id='start', dag=dag)
start_run = DummyOperator(task_id='start_run', dag=dag)
end = DummyOperator(task_id='end', dag=dag)

insert_new_record_into_audit_table = PythonOperator(
    task_id='insert_new_record_into_audit_table',
    python_callable=alert_notif_failure,
    op_kwargs={
        'dag_id': dag.dag_id,
        'task_id': 'insert_new_record_into_audit_table',
        'func': insert_into_audit_table_for_adhoc_data,
        'kwargs': {}
    },
    dag=dag
)

refresh_external_table = PythonOperator(
    task_id='refresh_external_table',
    python_callable=alert_notif_failure,
    op_kwargs={
        'dag_id': dag.dag_id,
        'task_id': 'refresh_external_table',
        'func': refresh_crm_campaign_run_external_table,
        'kwargs': {}
    },
    dag=dag
)

check_previous_run_status = BranchPythonOperator(
    task_id="check_previous_run_status",
    python_callable=alert_notif_failure,
    op_kwargs={
        'dag_id': dag.dag_id,
        'task_id': 'check_previous_run_status',
        'func': check_last_run_status,
        'kwargs': {
            'success_condition': 'start_run',
            'skip_condition': 'skip_run'
        }
    },
    dag=dag
)

skip_run_task = PythonOperator(
    task_id="skip_run",
    python_callable=alert_notif_skipped,
    op_kwargs={
        'dag_id': dag.dag_id,
        'task_id': 'skip_run',
    },
    dag=dag
)

check_data_in_stream = BranchPythonOperator(
    task_id="check_data_in_stream",
    python_callable=alert_notif_failure,
    op_kwargs={
        'dag_id': dag.dag_id,
        'task_id': 'check_data_in_stream',
        'func': check_data_in_stream_v2,
        'kwargs': {
            'success_condition': 'insert_new_record_into_audit_table',
            'skip_condition': 'skipped_due_to_data_unavailability'
        }
    },
    dag=dag
)
skipped_due_to_data_unavailability = PythonOperator(
    task_id="skipped_due_to_data_unavailability",
    python_callable=alert_notif_skipped,
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