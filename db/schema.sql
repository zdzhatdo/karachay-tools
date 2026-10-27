-- Karachay-Balkar corpus + lexicon schema (PostgreSQL 15+)
-- Layers: provenance -> corpus -> analysis -> lexicon -> media -> community -> ops

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Enums ---------------------------------------------------------------------

CREATE TYPE source_kind    AS ENUM ('wikipedia', 'news', 'literature', 'parallel', 'scan', 'family', 'other');
CREATE TYPE script_kind    AS ENUM ('cyrl', 'latn_1920s', 'latn_modern', 'arab');
CREATE TYPE dialect_kind   AS ENUM ('standard', 'karachay', 'baksan_chegem', 'malkar_cherek', 'unknown');
CREATE TYPE lang_label     AS ENUM ('krc', 'rus', 'tur', 'eng', 'other');
CREATE TYPE review_status  AS ENUM ('pending', 'approved', 'rejected');
CREATE TYPE consent_tier   AS ENUM ('public', 'research', 'family_only');
CREATE TYPE user_role      AS ENUM ('reader', 'contributor', 'reviewer', 'admin');

-- Users ---------------------------------------------------------------------

CREATE TABLE users (
    id            bigserial PRIMARY KEY,
    email         text UNIQUE NOT NULL,
    display_name  text NOT NULL,
    role          user_role NOT NULL DEFAULT 'contributor',
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- Provenance + corpus -------------------------------------------------------

CREATE TABLE sources (
    id            bigserial PRIMARY KEY,
    name          text UNIQUE NOT NULL,            -- e.g. 'krc_wikipedia'
    kind          source_kind NOT NULL,
    base_url      text,
    license       text NOT NULL,                   -- 'CC BY-SA 4.0', 'permission:2026-10', ...
    can_republish boolean NOT NULL DEFAULT false,  -- false => show snippets only
    notes         text
);

CREATE TABLE documents (
    id             bigserial PRIMARY KEY,
    source_id      bigint NOT NULL REFERENCES sources(id),
    url            text,
    title          text,
    script         script_kind NOT NULL DEFAULT 'cyrl',
    dialect        dialect_kind NOT NULL DEFAULT 'unknown',
    raw_sha256     char(64) NOT NULL,              -- points at immutable raw artifact
    published_at   date,
    fetched_at     timestamptz NOT NULL,
    ocr_confidence real,                           -- null for born-digital text
    metadata       jsonb NOT NULL DEFAULT '{}',
    UNIQUE (source_id, raw_sha256)
);

CREATE TABLE sentences (
    id              bigserial PRIMARY KEY,
    document_id     bigint NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    position        int NOT NULL,                  -- order within document
    text_original   text NOT NULL,                 -- as extracted
    text_norm       text NOT NULL,                 -- after normalization (canonical Cyrillic)
    text_sha256     char(64) NOT NULL,
    lang            lang_label NOT NULL,
    lang_confidence real NOT NULL,
    duplicate_of    bigint REFERENCES sentences(id),  -- null => canonical copy
    in_eval_set     boolean NOT NULL DEFAULT false,   -- held-out; never tune on these
    stage_versions  jsonb NOT NULL,                -- {"normalize":"1.3.0","segment":"1.0.2",...}
    UNIQUE (document_id, position)
);
CREATE INDEX sentences_hash_idx ON sentences (text_sha256);
CREATE INDEX sentences_lang_idx ON sentences (lang) WHERE duplicate_of IS NULL;
CREATE INDEX sentences_trgm_idx ON sentences USING gin (text_norm gin_trgm_ops);

CREATE TABLE sentence_translations (
    id           bigserial PRIMARY KEY,
    sentence_id  bigint NOT NULL REFERENCES sentences(id) ON DELETE CASCADE,
    lang         lang_label NOT NULL,
    text         text NOT NULL,
    origin       text NOT NULL,                    -- 'parallel_source', 'contributor', 'machine_draft'
    status       review_status NOT NULL DEFAULT 'pending',
    created_by   bigint REFERENCES users(id)
);

-- Tokens + analyses ---------------------------------------------------------

CREATE TABLE tokens (
    id           bigserial PRIMARY KEY,
    sentence_id  bigint NOT NULL REFERENCES sentences(id) ON DELETE CASCADE,
    position     int NOT NULL,
    form         text NOT NULL,                    -- surface form as written
    form_lower   text NOT NULL,
    char_start   int NOT NULL,                     -- offsets into text_norm, for highlighting
    char_end     int NOT NULL,
    is_word      boolean NOT NULL DEFAULT true,    -- false for punctuation/numbers
    UNIQUE (sentence_id, position)
);
CREATE INDEX tokens_form_idx ON tokens (form_lower);

CREATE TABLE analyzer_versions (
    id           serial PRIMARY KEY,
    tag          text UNIQUE NOT NULL,             -- 'krc-2026.10.2'
    git_sha      text NOT NULL,
    released_at  timestamptz NOT NULL DEFAULT now()
);

-- One row per candidate analysis. Unknown words have zero rows for the current version.
CREATE TABLE analyses (
    id            bigserial PRIMARY KEY,
    token_id      bigint NOT NULL REFERENCES tokens(id) ON DELETE CASCADE,
    analyzer_id   int NOT NULL REFERENCES analyzer_versions(id),
    lemma_text    text NOT NULL,
    lemma_id      bigint,                          -- FK added below, once lemmas exists
    tags          text[] NOT NULL,                 -- {'n','pl','px1pl','abl'}
    rank          smallint NOT NULL DEFAULT 1,     -- 1 = preferred after disambiguation
    is_gold       boolean NOT NULL DEFAULT false   -- human-verified
);
CREATE INDEX analyses_token_idx ON analyses (token_id, analyzer_id);
CREATE INDEX analyses_tags_idx  ON analyses USING gin (tags);
CREATE INDEX analyses_lemma_idx ON analyses (lemma_id);

-- Lexicon -------------------------------------------------------------------

CREATE TABLE lemmas (
    id           bigserial PRIMARY KEY,
    headword     text NOT NULL,                    -- canonical Cyrillic
    pos          text NOT NULL,                    -- matches analyzer tag set: 'n','v','adj',...
    dialect      dialect_kind NOT NULL DEFAULT 'standard',
    etymology    text,
    notes        text,
    status       review_status NOT NULL DEFAULT 'pending',
    in_analyzer  boolean NOT NULL DEFAULT false,   -- exported to lexc?
    created_by   bigint REFERENCES users(id),
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (headword, pos, dialect)
);
CREATE INDEX lemmas_headword_trgm ON lemmas USING gin (headword gin_trgm_ops);

ALTER TABLE analyses
    ADD CONSTRAINT analyses_lemma_fk FOREIGN KEY (lemma_id) REFERENCES lemmas(id);

CREATE TABLE senses (
    id           bigserial PRIMARY KEY,
    lemma_id     bigint NOT NULL REFERENCES lemmas(id) ON DELETE CASCADE,
    position     smallint NOT NULL,
    gloss_lang   lang_label NOT NULL,              -- glosses in rus / tur / eng
    gloss        text NOT NULL,
    status       review_status NOT NULL DEFAULT 'pending',
    UNIQUE (lemma_id, gloss_lang, position)
);
CREATE INDEX senses_gloss_trgm ON senses USING gin (gloss gin_trgm_ops);  -- English/Russian -> Karachay search

CREATE TABLE lemma_relations (
    from_lemma   bigint NOT NULL REFERENCES lemmas(id) ON DELETE CASCADE,
    to_lemma     bigint NOT NULL REFERENCES lemmas(id) ON DELETE CASCADE,
    relation     text NOT NULL,                    -- 'derived_from','synonym','dialect_variant','turkish_cognate'
    PRIMARY KEY (from_lemma, to_lemma, relation)
);

CREATE TABLE cognates (                            -- bridge to Turkish (and others) without full lemmas
    id           bigserial PRIMARY KEY,
    lemma_id     bigint NOT NULL REFERENCES lemmas(id) ON DELETE CASCADE,
    lang         lang_label NOT NULL,
    word         text NOT NULL,
    false_friend boolean NOT NULL DEFAULT false,
    note         text
);

-- Media (audio) -------------------------------------------------------------

CREATE TABLE speakers (
    id             bigserial PRIMARY KEY,
    display_name   text,                           -- may be null / pseudonymous
    birth_decade   smallint,
    home_region    text,
    dialect        dialect_kind NOT NULL DEFAULT 'unknown',
    consent        consent_tier NOT NULL,
    consent_doc    text NOT NULL,                  -- pointer to signed/recorded consent
    withdrawn_at   timestamptz                     -- set => hide all their recordings
);

CREATE TABLE recordings (
    id            bigserial PRIMARY KEY,
    speaker_id    bigint NOT NULL REFERENCES speakers(id),
    storage_key   text NOT NULL,                   -- object storage path, never public URL
    duration_ms   int NOT NULL,
    consent       consent_tier NOT NULL,           -- may be stricter than speaker default
    lemma_id      bigint REFERENCES lemmas(id),
    sentence_id   bigint REFERENCES sentences(id),
    transcript    text,
    recorded_at   timestamptz,
    CHECK (lemma_id IS NOT NULL OR sentence_id IS NOT NULL OR transcript IS NOT NULL)
);

-- Community review + audit --------------------------------------------------

CREATE TABLE suggestions (
    id           bigserial PRIMARY KEY,
    author_id    bigint NOT NULL REFERENCES users(id),
    target_table text NOT NULL,                    -- 'lemmas','senses','analyses',...
    target_id    bigint,                           -- null => proposing a new row
    payload      jsonb NOT NULL,                   -- proposed values
    comment      text,
    status       review_status NOT NULL DEFAULT 'pending',
    reviewer_id  bigint REFERENCES users(id),
    reviewed_at  timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX suggestions_queue_idx ON suggestions (status, created_at);

CREATE TABLE audit_log (                           -- append-only; written by triggers or the API
    id          bigserial PRIMARY KEY,
    actor_id    bigint REFERENCES users(id),       -- null => pipeline/system
    action      text NOT NULL,                     -- 'insert','update','delete','approve'
    table_name  text NOT NULL,
    row_id      bigint NOT NULL,
    before      jsonb,
    after       jsonb,
    at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_row_idx ON audit_log (table_name, row_id, at);

-- Ops: pipeline runs + evaluation ------------------------------------------

CREATE TABLE pipeline_runs (
    id            bigserial PRIMARY KEY,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    git_sha       text NOT NULL,
    analyzer_id   int REFERENCES analyzer_versions(id),
    sources       text[] NOT NULL,
    stats         jsonb NOT NULL DEFAULT '{}'      -- counts per stage, errors, timings
);

CREATE TABLE eval_runs (
    id              bigserial PRIMARY KEY,
    run_at          timestamptz NOT NULL DEFAULT now(),
    analyzer_id     int NOT NULL REFERENCES analyzer_versions(id),
    eval_set        text NOT NULL,                 -- 'heldout-v1'
    token_coverage  numeric(5,2) NOT NULL,         -- % of running words analyzed
    type_coverage   numeric(5,2) NOT NULL,         -- % of unique words analyzed
    gold_accuracy   numeric(5,2),                  -- % matching human-verified analyses
    per_source      jsonb NOT NULL DEFAULT '{}',
    regressions     int NOT NULL DEFAULT 0
);

-- Derived views -------------------------------------------------------------

-- Word frequency over canonical Karachay sentences (refresh after each pipeline run)
CREATE MATERIALIZED VIEW word_frequency AS
SELECT t.form_lower, count(*) AS freq
FROM tokens t
JOIN sentences s ON s.id = t.sentence_id
WHERE t.is_word AND s.lang = 'krc' AND s.duplicate_of IS NULL AND NOT s.in_eval_set
GROUP BY t.form_lower;
CREATE UNIQUE INDEX ON word_frequency (form_lower);

-- The lexicon to-do list: frequent words the latest analyzer can't parse
CREATE MATERIALIZED VIEW unknown_words AS
WITH latest AS (SELECT id FROM analyzer_versions ORDER BY released_at DESC LIMIT 1)
SELECT wf.form_lower, wf.freq
FROM word_frequency wf
WHERE NOT EXISTS (
    SELECT 1
    FROM tokens t
    JOIN analyses a ON a.token_id = t.id
    WHERE t.form_lower = wf.form_lower
      AND a.analyzer_id = (SELECT id FROM latest)
)
ORDER BY wf.freq DESC;
