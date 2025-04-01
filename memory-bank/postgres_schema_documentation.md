# Документация схемы PostgreSQL базы данных (MCP стандарт)

## Таблица users
```sql
CREATE TABLE users (
    id uuid PRIMARY KEY,
    id_home_item uuid REFERENCES items(id),
    login_name text NOT NULL,
    displayed_name text NOT NULL,
    email text,
    telephone_num text,
    pwd_hash bytea,
    flags integer NOT NULL DEFAULT 0,
    created_by uuid REFERENCES users(id),
    time_registered timestamptz,
    last_login timestamptz
);

COMMENT ON TABLE users IS 'Хранение данных пользователей системы';
COMMENT ON COLUMN users.flags IS 'Битовая маска флагов: 1-активен, 2-заблокирован, 4-админ';
```

## Таблица items
```sql
CREATE TABLE items (
    id uuid PRIMARY KEY,
    id_parent uuid REFERENCES items(id),
    id_portal uuid,
    area real,
    txt text,
    file_hash bytea REFERENCES files(hash),
    file_name text,
    lay_type smallint,
    lay_cols integer,
    lay_propagate boolean,
    style bytea,
    children bytea,
    rights bytea,
    attr jsonb
);

CREATE INDEX idx_items_parent ON items(id_parent);
```

## Таблица files
```sql
CREATE TABLE files (
    hash bytea PRIMARY KEY,
    body bytea
);

COMMENT ON TABLE files IS 'Хранение файлов системы';
```

## Таблица thumbnails
```sql
CREATE TABLE thumbnails (
    file_hash bytea NOT NULL,
    size integer NOT NULL,
    bigger_exists boolean NOT NULL,
    body bytea,
    PRIMARY KEY (file_hash, size)
);

COMMENT ON TABLE thumbnails IS 'Превью файлов различных размеров';
```

## Таблица thumbnails_queue
```sql
CREATE TABLE thumbnails_queue (
    id bigint PRIMARY KEY DEFAULT nextval('thumbnails_queue_id_seq'::regclass),
    file_hash bytea,
    file_name text
);
```

## Таблица log_auth
```sql
CREATE TABLE log_auth (
    id bigint PRIMARY KEY DEFAULT nextval('log_auth_id_seq'::regclass),
    uname text NOT NULL,
    address inet NOT NULL,
    start timestamptz NOT NULL,
    finish timestamptz
);

CREATE INDEX idx_log_auth_uname ON log_auth(uname);
```

## Таблица log_bad_auth
```sql
CREATE TABLE log_bad_auth (
    id bigint PRIMARY KEY DEFAULT nextval('log_bad_auth_id_seq'::regclass),
    tm timestamptz NOT NULL,
    login text NOT NULL,
    pwd text NOT NULL,
    address inet NOT NULL,
    reason text
);
```

## Таблица log_item_access
```sql
CREATE TABLE log_item_access (
    item_id uuid,
    tm timestamptz NOT NULL,
    uname text,
    type smallint NOT NULL
);

CREATE INDEX idx_log_item_access_item ON log_item_access(item_id);
```

## Таблица embeddings
```sql
CREATE TABLE embeddings (
    id integer PRIMARY KEY DEFAULT nextval('embeddings_id_seq'::regclass),
    item_id varchar NOT NULL,
    text text NOT NULL,
    text_hash varchar NOT NULL,
    embedding vector,
    dimensions integer NOT NULL,
    model varchar NOT NULL,
    model_version varchar NOT NULL,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE embeddings IS 'Векторные представления контента';
```

## Таблица query_embeddings
```sql
CREATE TABLE query_embeddings (
    id integer PRIMARY KEY DEFAULT nextval('query_embeddings_id_seq'::regclass),
    text text NOT NULL,
    text_hash varchar NOT NULL,
    embedding vector,
    dimensions integer NOT NULL,
    model varchar NOT NULL,
    model_version varchar NOT NULL,
    frequency integer DEFAULT 1,
    last_used timestamp DEFAULT CURRENT_TIMESTAMP,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP
);
```

## Таблица user_groups
```sql
CREATE TABLE user_groups (
    id_group uuid NOT NULL,
    id_user uuid NOT NULL,
    PRIMARY KEY (id_group, id_user)
);
```

## Полная схема связей
- thumbnails.file_hash → files.hash
- thumbnails_queue.file_hash → files.hash
- log_auth.uname → users.login_name
- log_bad_auth.login → users.login_name
- log_item_access.item_id → items.id
- log_item_access.uname → users.login_name
- users.id_home_item → items.id
- users.created_by → users.id
- items.id_parent → items.id
- items.file_hash → files.hash
- user_groups.id_user → users.id

## Примеры запросов
```sql
-- Получить список пользователей с их домашними элементами
SELECT u.login_name, i.file_name 
FROM users u
LEFT JOIN items i ON u.id_home_item = i.id;

-- Получить 10 последних авторизованных пользователей
SELECT u.login_name, la.address, la.start
FROM users u
JOIN log_auth la ON u.login_name = la.uname
ORDER BY la.start DESC
LIMIT 10;