use rusqlite::Connection;
use crate::utils::error_handler::Result;

pub const CURRENT_SCHEMA_VERSION: i32 = 1;

pub fn apply_migrations(conn: &mut Connection) -> Result<()> {
    let current_ver: i32 = conn.query_row("PRAGMA user_version", [], |row| row.get(0))?;

    if current_ver < 1 {
        let tx = conn.transaction()?;

        // files table
        tx.execute(
            "CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rel_path TEXT NOT NULL,
                abs_path TEXT NOT NULL,
                size INTEGER NOT NULL,
                mtime INTEGER NOT NULL,
                hash_sha256 TEXT,
                folder_root_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pendente',
                origem_original TEXT,
                first_seen INTEGER NOT NULL,
                last_seen INTEGER NOT NULL,
                marked_for_deletion INTEGER NOT NULL DEFAULT 0,
                marked_at INTEGER,
                UNIQUE(folder_root_id, rel_path)
            )",
            [],
        )?;

        // indexes on files
        tx.execute("CREATE INDEX IF NOT EXISTS idx_files_hash ON files(hash_sha256)", [])?;
        tx.execute("CREATE INDEX IF NOT EXISTS idx_files_size ON files(size)", [])?;
        tx.execute("CREATE INDEX IF NOT EXISTS idx_files_status ON files(status)", [])?;
        tx.execute("CREATE INDEX IF NOT EXISTS idx_files_marked ON files(marked_for_deletion)", [])?;

        // tags table
        tx.execute(
            "CREATE TABLE IF NOT EXISTS tags (
                id TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                caminho_fisico TEXT NOT NULL,
                origem TEXT NOT NULL,
                categoria TEXT NOT NULL,
                subcategoria TEXT,
                entidade TEXT,
                palavras_chave TEXT,
                confianca_base REAL DEFAULT 1.0,
                usar_para_automacao INTEGER DEFAULT 1,
                version INTEGER DEFAULT 1,
                idioma TEXT DEFAULT '',
                sinonimos TEXT DEFAULT '[]'
            )",
            [],
        )?;

        // classification_cache table
        tx.execute(
            "CREATE TABLE IF NOT EXISTS classification_cache (
                file_id INTEGER UNIQUE NOT NULL,
                tag_id TEXT,
                confianca REAL NOT NULL,
                rules_version TEXT NOT NULL,
                texto_hash TEXT,
                texto TEXT,
                FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
            )",
            [],
        )?;
        tx.execute("CREATE INDEX IF NOT EXISTS idx_cache_rules ON classification_cache(rules_version)", [])?;

        // folder_roots table
        tx.execute(
            "CREATE TABLE IF NOT EXISTS folder_roots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                root_rel TEXT NOT NULL,
                root_abs TEXT NOT NULL UNIQUE,
                volume_serial TEXT,
                last_scan INTEGER
            )",
            [],
        )?;

        // FTS5 tables
        tx.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS fts_files USING fts5(
                rel_path,
                tag,
                entidade,
                palavras_chave,
                snippet,
                data_ini,
                data_fim,
                tokenize = 'unicode61'
            )",
            [],
        )?;

        tx.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS fts_numbers USING fts5(
                cpf,
                cnpj,
                boleto,
                rel_path,
                tokenize = 'trigram'
            )",
            [],
        )?;

        tx.execute(&format!("PRAGMA user_version = {}", CURRENT_SCHEMA_VERSION), [])?;
        tx.commit()?;
    }

    Ok(())
}
