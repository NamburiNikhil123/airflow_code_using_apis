from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from airflow.operators.dummy import DummyOperator
from helper_functions import HelperFunctions

helper = HelperFunctions()

default_args = {
    'owner': 'airflow',
    'retries': 5,
    'retry_delay': timedelta(minutes=1)
}

dag = DAG(
    dag_id='alerting_all_dags_using_apis',
    default_args=default_args,
    description="Check all the DAGs that are active and check the latest runs of each active DAGs and based on the state Alert to Slack",
    schedule_interval='*/3 * * * *',
    start_date=datetime(2024, 6, 18),
    catchup=False,
)

start = DummyOperator(task_id='start', dag=dag)
end = DummyOperator(task_id='end', dag=dag)

get_all_active_dags_task = PythonOperator(
    task_id="get_all_active_dags",
    python_callable=helper.alert_notif_failure_api,
    op_kwargs={
        'dag_id': dag.dag_id,
        'task_id': 'get_all_active_dags',
        'func': helper.get_all_active_dags,
        'kwargs': {}
    },
    dag=dag 
)

get_all_dag_ids_last_limit_run_ids_task = PythonOperator(
    task_id="get_all_dag_ids_last_limit_run_ids",
    python_callable=helper.alert_notif_failure_api,
    op_kwargs={
        'dag_id': dag.dag_id,
        'task_id': 'get_all_dag_ids_last_limit_run_ids',
        'func': helper.get_all_dag_ids_last_limit_run_ids,
        'kwargs': {
            'active_dag_ids': get_all_active_dags_task.output
        }
    },
    dag=dag
)

get_all_dagruns_task_instances_task = PythonOperator(
    task_id="get_all_dagruns_task_instances",
    python_callable=helper.alert_notif_failure_api,
    op_kwargs={
        'dag_id': dag.dag_id,
        'task_id': 'get_all_dagruns_task_instances',
        'func': helper.get_all_dagruns_task_instances,
        'kwargs': {
            'run_ids': get_all_dag_ids_last_limit_run_ids_task.output
        }
    },
    dag=dag
)

alert_all_continuous_skipped_dags_task = PythonOperator(
    task_id="alert_all_continuous_skipped_dags",
    python_callable=helper.alert_notif_failure_api,
    op_kwargs={
        'dag_id': dag.dag_id,
        'task_id': 'alert_all_continuous_skipped_dags',
        'func': helper.alert_all_continuous_skipped_dags,
        'kwargs': {
            'states_of_all_dags_each_runs': get_all_dagruns_task_instances_task.output
        }
    },
    dag=dag
)

start >> get_all_active_dags_task >> get_all_dag_ids_last_limit_run_ids_task >> get_all_dagruns_task_instances_task >> alert_all_continuous_skipped_dags_task >> end
