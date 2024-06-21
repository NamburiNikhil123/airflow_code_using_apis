from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from airflow.operators.dummy import DummyOperator
from helper_functions import get_all_active_dags, get_all_dag_ids_last_limit_run_ids, get_all_dagruns_task_instances, alert_all_continuous_skipped_dags

default_args = {
    'owner': 'airflow',
    'retries': 5,
    'retry_delay': timedelta(minutes=1)
}

dag = DAG(
    dag_id='alerting_all_dags_using_apis',
    default_args=default_args,
    description="Check all the DAGs that are active and check the latest runs of each active DAGs and based on the state Alert to Slack",
    schedule_interval='*/15 * * * *',
    start_date=datetime(2024, 6, 18),
    catchup=False,
)

start = DummyOperator(task_id='start', dag=dag)
end = DummyOperator(task_id='end', dag=dag)

get_all_active_dags_task = PythonOperator(
    task_id="get_all_active_dags",
    python_callable=get_all_active_dags,
    dag=dag 
)

get_all_dag_ids_last_limit_run_ids_task = PythonOperator(
    task_id="get_all_dag_ids_last_limit_run_ids",
    python_callable=get_all_dag_ids_last_limit_run_ids,
    op_args=[get_all_active_dags_task.output],  # Pass the output of the previous task
    dag=dag
)

get_all_dagruns_task_instances_task = PythonOperator(
    task_id="get_all_dagruns_task_instances",
    python_callable=get_all_dagruns_task_instances,
    op_args=[get_all_dag_ids_last_limit_run_ids_task.output],  # Pass the output of the previous task
    dag=dag
)

alert_all_continuous_skipped_dags_task = PythonOperator(
    task_id="alert_all_continuous_skipped_dags",
    python_callable=alert_all_continuous_skipped_dags,
    op_args=[get_all_dagruns_task_instances_task.output],  # Pass the output of the previous task
    dag=dag
)

start >> get_all_active_dags_task >> get_all_dag_ids_last_limit_run_ids_task >> get_all_dagruns_task_instances_task >> alert_all_continuous_skipped_dags_task >> end
