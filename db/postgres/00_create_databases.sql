-- Run against the default `asie_app` connection (the only DB that exists
-- at RDS creation time). Creates the two additional databases plus one
-- least-privilege role per workload, each granted only on its own database.
-- CREATE DATABASE can't run inside a transaction and Postgres has no
-- CREATE DATABASE IF NOT EXISTS, hence the \gexec guard pattern.

SELECT 'CREATE DATABASE airflow_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow_db')\gexec

SELECT 'CREATE DATABASE mlflow_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mlflow_db')\gexec

-- Create-if-absent, then ALWAYS set the password.
--
-- Creating with the password inline and skipping existing roles looks
-- idempotent but isn't: the roles live in RDS while the passwords live in a
-- Kubernetes Secret, and those have different lifetimes. `asie.sh pause`
-- deletes the cluster (and the Secret) while RDS survives, so the next run
-- generates fresh passwords, finds the roles already present, skips CREATE --
-- and the new password is never applied. Every workload then fails to
-- authenticate with no indication why. The unconditional ALTER re-syncs the
-- role to whatever password this run is using.
SELECT 'CREATE ROLE asie_app_user LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'asie_app_user')\gexec
ALTER ROLE asie_app_user LOGIN PASSWORD :'asie_app_user_password';

SELECT 'CREATE ROLE airflow_user LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'airflow_user')\gexec
ALTER ROLE airflow_user LOGIN PASSWORD :'airflow_user_password';

SELECT 'CREATE ROLE mlflow_user LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mlflow_user')\gexec
ALTER ROLE mlflow_user LOGIN PASSWORD :'mlflow_user_password';

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
