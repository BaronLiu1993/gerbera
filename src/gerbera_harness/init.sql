CREATE USER gerbera_schema_owner
WITH
    PASSWORD 'schema_password'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE;


CREATE USER gerbera_writer
WITH
    PASSWORD 'writer_password'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE;


CREATE USER gerbera_reader
WITH
    PASSWORD 'reader_password'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE;

GRANT CONNECT ON DATABASE gerbera
TO gerbera_schema_owner,
   gerbera_writer,
   gerbera_reader;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

GRANT CREATE, USAGE ON SCHEMA public
TO gerbera_schema_owner;

GRANT USAGE ON SCHEMA public
TO gerbera_writer,
   gerbera_reader;

GRANT INSERT ON ALL TABLES IN SCHEMA public
TO gerbera_writer;

GRANT SELECT ON ALL TABLES IN SCHEMA public
TO gerbera_reader;

GRANT USAGE ON ALL SEQUENCES IN SCHEMA public
TO gerbera_writer;

ALTER DEFAULT PRIVILEGES
FOR ROLE gerbera_schema_owner
IN SCHEMA public
GRANT INSERT ON TABLES
TO gerbera_writer;

ALTER DEFAULT PRIVILEGES
FOR ROLE gerbera_schema_owner
IN SCHEMA public
GRANT SELECT ON TABLES
TO gerbera_reader;

ALTER DEFAULT PRIVILEGES
FOR ROLE gerbera_schema_owner
IN SCHEMA public
GRANT USAGE ON SEQUENCES
TO gerbera_writer;