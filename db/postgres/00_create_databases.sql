-- Run against the default `asie_app` connection (the only DB that exists
-- at RDS creation time). Creates the two additional databases plus one
-- least-privilege role per workload, each granted only on its own database.
-- CREATE DATABASE can't run inside a transaction and Postgres has no
-- CREATE DATABASE IF NOT EXISTS, hence the \gexec guard pattern.

SELECT 'CREATE DATABASE airflow_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow_db')\gexec

SELECT 'CREATE DATABASE mlflow_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mlflow_db')\gexec

SELECT 'CREATE ROLE asie_app_user LOGIN PASSWORD ''' || :'asie_app_user_password' || ''''
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'asie_app_user')\gexec

SELECT 'CREATE ROLE airflow_user LOGIN PASSWORD ''' || :'airflow_user_password' || ''''
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'airflow_user')\gexec

SELECT 'CREATE ROLE mlflow_user LOGIN PASSWORD ''' || :'mlflow_user_password' || ''''
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mlflow_user')\gexec

GRANT ALL PRIVILEGES ON DATABASE asie_app TO asie_app_user;
GRANT ALL PRIVILEGES ON DATABASE airflow_db TO airflow_user;
GRANT ALL PRIVILEGES ON DATABASE mlflow_db TO mlflow_user;

-- Postgres 15+ requires an explicit per-database schema grant too (the
-- public schema is no longer world-writable by default) — each one has to
-- run while actually connected to that database, hence the \c hops. The
-- bootstrap Job runs this and 10_/11_ (which create asie_app's tables) in
-- the same psql session, so this must land back on asie_app at the end.
\c airflow_db
GRANT ALL ON SCHEMA public TO airflow_user;

\c mlflow_db
GRANT ALL ON SCHEMA public TO mlflow_user;

\c asie_app
GRANT ALL ON SCHEMA public TO asie_app_user;
