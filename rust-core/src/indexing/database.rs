use std::path::Path;
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use crate::utils::error_handler::{IndexoError, Result};
use crate::indexing::migrations::apply_migrations;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DbFile {
    pub id: i64,
    pub rel_path: String,
    pub abs_path: String,
    pub size: i64,
    pub mtime: i64,
    pub hash_sha256: Option<String>,
    pub folder_root_id: i64,
    pub status: String,
    pub origem_original: Option<String>,
    pub first_seen: i64,
    pub last_seen: i64,
    pub marked_for_deletion: bool,
    pub marked_at: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DbTag {
    pub id: String,
    pub nome: String,
    pub caminho_fisico: String,
    pub origem: String,
    pub categoria: String,
    pub subcategoria: Option<String>,
    pub entidade: Option<String>,
    pub palavras_chave: Option<String>,
    pub confianca_base: f64,
    pub usar_para_automacao: bool,
    pub version: i32,
    pub idioma: String,
    pub sinonimos: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    pub rel_path: String,
    pub tag: String,
    pub entidade: String,
    pub snippet: String,
    pub match_type: String,
}

pub struct IndexoDatabase {
    pub conn: Connection,
}

impl IndexoDatabase {
    pub fn open<P: AsRef<Path>>(path: P) -> Result<Self> {
        let path_ref = path.as_ref();
        if let Some(parent) = path_ref.parent() {
            std::fs::create_dir_all(parent)?;
        }

        // Daily backup if db exists
        if path_ref.exists() {
            let bak_path = path_ref.with_extension("db.bak");
            let _ = std::fs::copy(path_ref, bak_path);
        }

        let mut conn = Connection::open(path_ref)?;
        let _ = conn.query_row("PRAGMA journal_mode = WAL", [], |_| Ok(()));
        let _ = conn.execute("PRAGMA synchronous = NORMAL", []);
        let _ = conn.execute("PRAGMA foreign_keys = ON", []);

        apply_migrations(&mut conn)?;

        Ok(Self { conn })
    }

    pub fn check_integrity(&self) -> Result<bool> {
        let status: String = self.conn.query_row("PRAGMA integrity_check", [], |row| row.get(0))?;
        Ok(status == "ok")
    }

    pub fn get_or_create_root(&mut self, root_abs: &str, root_rel: &str) -> Result<i64> {
        let now = chrono::Utc::now().timestamp();
        let existing = self.conn.query_row(
            "SELECT id FROM folder_roots WHERE root_abs = ?1",
            params![root_abs],
            |row| row.get(0),
        );

        match existing {
            Ok(id) => {
                self.conn.execute(
                    "UPDATE folder_roots SET last_scan = ?1 WHERE id = ?2",
                    params![now, id],
                )?;
                Ok(id)
            }
            Err(_) => {
                self.conn.execute(
                    "INSERT INTO folder_roots (root_rel, root_abs, last_scan) VALUES (?1, ?2, ?3)",
                    params![root_rel, root_abs, now],
                )?;
                Ok(self.conn.last_insert_rowid())
            }
        }
    }

    pub fn upsert_file(
        &mut self,
        root_id: i64,
        rel_path: &str,
        abs_path: &str,
        size: i64,
        mtime: i64,
        hash: Option<&str>,
        status: &str,
    ) -> Result<i64> {
        let now = chrono::Utc::now().timestamp();
        self.conn.execute(
            "INSERT INTO files (folder_root_id, rel_path, abs_path, size, mtime, hash_sha256, status, first_seen, last_seen)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?8)
             ON CONFLICT(folder_root_id, rel_path) DO UPDATE SET
                abs_path = excluded.abs_path,
                size = excluded.size,
                mtime = excluded.mtime,
                hash_sha256 = COALESCE(excluded.hash_sha256, files.hash_sha256),
                last_seen = excluded.last_seen",
            params![root_id, rel_path, abs_path, size, mtime, hash, status, now],
        )?;

        let id: i64 = self.conn.query_row(
            "SELECT id FROM files WHERE folder_root_id = ?1 AND rel_path = ?2",
            params![root_id, rel_path],
            |row| row.get(0),
        )?;
        Ok(id)
    }

    pub fn get_file_by_id(&self, file_id: i64) -> Result<Option<DbFile>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, rel_path, abs_path, size, mtime, hash_sha256, folder_root_id, status, origem_original, first_seen, last_seen, marked_for_deletion, marked_at
             FROM files WHERE id = ?1",
        )?;

        let file = stmt.query_row(params![file_id], |row| {
            Ok(DbFile {
                id: row.get(0)?,
                rel_path: row.get(1)?,
                abs_path: row.get(2)?,
                size: row.get(3)?,
                mtime: row.get(4)?,
                hash_sha256: row.get(5)?,
                folder_root_id: row.get(6)?,
                status: row.get(7)?,
                origem_original: row.get(8)?,
                first_seen: row.get(9)?,
                last_seen: row.get(10)?,
                marked_for_deletion: row.get::<_, i32>(11)? != 0,
                marked_at: row.get(12)?,
            })
        });

        match file {
            Ok(f) => Ok(Some(f)),
            Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
            Err(e) => Err(IndexoError::from(e)),
        }
    }

    pub fn mark_for_deletion(&mut self, file_id: i64, marked: bool) -> Result<()> {
        let now = if marked { Some(chrono::Utc::now().timestamp()) } else { None };
        let marked_int = if marked { 1 } else { 0 };
        self.conn.execute(
            "UPDATE files SET marked_for_deletion = ?1, marked_at = ?2 WHERE id = ?3",
            params![marked_int, now, file_id],
        )?;
        Ok(())
    }

    pub fn list_marked_for_deletion(&self) -> Result<Vec<DbFile>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, rel_path, abs_path, size, mtime, hash_sha256, folder_root_id, status, origem_original, first_seen, last_seen, marked_for_deletion, marked_at
             FROM files WHERE marked_for_deletion = 1 ORDER BY marked_at DESC",
        )?;

        let rows = stmt.query_map([], |row| {
            Ok(DbFile {
                id: row.get(0)?,
                rel_path: row.get(1)?,
                abs_path: row.get(2)?,
                size: row.get(3)?,
                mtime: row.get(4)?,
                hash_sha256: row.get(5)?,
                folder_root_id: row.get(6)?,
                status: row.get(7)?,
                origem_original: row.get(8)?,
                first_seen: row.get(9)?,
                last_seen: row.get(10)?,
                marked_for_deletion: true,
                marked_at: row.get(12)?,
            })
        })?;

        let mut list = Vec::new();
        for r in rows {
            list.push(r?);
        }
        Ok(list)
    }

    pub fn delete_file_record(&mut self, file_id: i64) -> Result<()> {
        let rel_path: Option<String> = self.conn.query_row(
            "SELECT rel_path FROM files WHERE id = ?1",
            params![file_id],
            |r| r.get(0),
        ).ok();

        if let Some(ref path) = rel_path {
            let _ = self.conn.execute("DELETE FROM fts_files WHERE rel_path = ?1", params![path]);
            let _ = self.conn.execute("DELETE FROM fts_numbers WHERE rel_path = ?1", params![path]);
        }

        self.conn.execute("DELETE FROM classification_cache WHERE file_id = ?1", params![file_id])?;
        self.conn.execute("DELETE FROM files WHERE id = ?1", params![file_id])?;
        Ok(())
    }

    pub fn find_duplicates(&self, root_id: i64) -> Result<Vec<Vec<DbFile>>> {
        let mut stmt = self.conn.prepare(
            "SELECT hash_sha256 FROM files 
             WHERE folder_root_id = ?1 AND hash_sha256 IS NOT NULL AND hash_sha256 != ''
             GROUP BY hash_sha256 HAVING COUNT(*) > 1",
        )?;

        let hashes: Vec<String> = stmt
            .query_map(params![root_id], |row| row.get(0))?
            .filter_map(|r| r.ok())
            .collect();

        let mut groups = Vec::new();
        for hash in hashes {
            let mut file_stmt = self.conn.prepare(
                "SELECT id, rel_path, abs_path, size, mtime, hash_sha256, folder_root_id, status, origem_original, first_seen, last_seen, marked_for_deletion, marked_at
                 FROM files WHERE folder_root_id = ?1 AND hash_sha256 = ?2",
            )?;

            let files: Vec<DbFile> = file_stmt
                .query_map(params![root_id, hash], |row| {
                    Ok(DbFile {
                        id: row.get(0)?,
                        rel_path: row.get(1)?,
                        abs_path: row.get(2)?,
                        size: row.get(3)?,
                        mtime: row.get(4)?,
                        hash_sha256: row.get(5)?,
                        folder_root_id: row.get(6)?,
                        status: row.get(7)?,
                        origem_original: row.get(8)?,
                        first_seen: row.get(9)?,
                        last_seen: row.get(10)?,
                        marked_for_deletion: row.get::<_, i32>(11)? != 0,
                        marked_at: row.get(12)?,
                    })
                })?
                .filter_map(|r| r.ok())
                .collect();

            if files.len() > 1 {
                groups.push(files);
            }
        }

        Ok(groups)
    }

    pub fn search_fts(&self, query: &str) -> Result<Vec<SearchResult>> {
        let mut results = Vec::new();
        let clean_query = query.trim();
        if clean_query.is_empty() {
            return Ok(results);
        }

        // 1. FTS text search with multi-word prefix matching
        let terms: Vec<String> = clean_query
            .split_whitespace()
            .map(|w| {
                let escaped = w.replace('"', "").replace('*', "");
                if escaped.is_empty() {
                    String::new()
                } else {
                    format!("\"{}\"*", escaped)
                }
            })
            .filter(|s| !s.is_empty())
            .collect();

        let fts_query = if terms.is_empty() {
            format!("\"{}\"*", clean_query.replace('"', "").replace('*', ""))
        } else {
            terms.join(" ")
        };

        let mut stmt = self.conn.prepare(
            "SELECT rel_path, tag, entidade, snippet FROM fts_files WHERE fts_files MATCH ?1 LIMIT 50",
        )?;

        if let Ok(rows) = stmt.query_map(params![fts_query], |row| {
            Ok(SearchResult {
                rel_path: row.get(0)?,
                tag: row.get(1)?,
                entidade: row.get(2)?,
                snippet: row.get(3)?,
                match_type: "fts_text".to_string(),
            })
        }) {
            for r in rows.flatten() {
                results.push(r);
            }
        }

        // 2. FTS trigram numbers search
        let trigram_query = format!("\"{}\"", clean_query.replace('"', ""));
        let mut num_stmt = self.conn.prepare(
            "SELECT rel_path, cpf, cnpj, boleto FROM fts_numbers WHERE fts_numbers MATCH ?1 LIMIT 50",
        )?;
        if let Ok(rows) = num_stmt.query_map(params![trigram_query], |row| {
            let rel_path: String = row.get(0)?;
            let cpf: String = row.get(1)?;
            let cnpj: String = row.get(2)?;
            let boleto: String = row.get(3)?;
            let snip = format!("{} {} {}", cpf, cnpj, boleto).trim().to_string();
            Ok(SearchResult {
                rel_path,
                tag: String::new(),
                entidade: String::new(),
                snippet: snip,
                match_type: "trigram_number".to_string(),
            })
        }) {
            for r in rows.flatten() {
                if !results.iter().any(|item| item.rel_path == r.rel_path) {
                    results.push(r);
                }
            }
        }

        // 3. Fallback direct match on files table (LIKE %query%)
        let like_pattern = format!("%{}%", clean_query);
        let mut file_stmt = self.conn.prepare(
            "SELECT rel_path FROM files WHERE rel_path LIKE ?1 LIMIT 30",
        )?;
        if let Ok(rows) = file_stmt.query_map(params![like_pattern], |row| {
            let rel_path: String = row.get(0)?;
            Ok(SearchResult {
                rel_path: rel_path.clone(),
                tag: "Arquivo".to_string(),
                entidade: String::new(),
                snippet: rel_path,
                match_type: "path_like".to_string(),
            })
        }) {
            for r in rows.flatten() {
                if !results.iter().any(|item| item.rel_path == r.rel_path) {
                    results.push(r);
                }
            }
        }

        Ok(results)
    }

    pub fn update_fts_content(
        &mut self,
        rel_path: &str,
        tag: &str,
        entidade: &str,
        palavras_chave: &str,
        snippet: &str,
        cpf: &str,
        cnpj: &str,
        boleto: &str,
    ) -> Result<()> {
        let _ = self.conn.execute("DELETE FROM fts_files WHERE rel_path = ?1", params![rel_path]);
        let _ = self.conn.execute("DELETE FROM fts_numbers WHERE rel_path = ?1", params![rel_path]);

        self.conn.execute(
            "INSERT INTO fts_files (rel_path, tag, entidade, palavras_chave, snippet) VALUES (?1, ?2, ?3, ?4, ?5)",
            params![rel_path, tag, entidade, palavras_chave, snippet],
        )?;

        if !cpf.is_empty() || !cnpj.is_empty() || !boleto.is_empty() {
            self.conn.execute(
                "INSERT INTO fts_numbers (rel_path, cpf, cnpj, boleto) VALUES (?1, ?2, ?3, ?4)",
                params![rel_path, cpf, cnpj, boleto],
            )?;
        }

        Ok(())
    }

    pub fn clear_content_privacy(&mut self) -> Result<()> {
        self.conn.execute("DELETE FROM fts_files", [])?;
        self.conn.execute("DELETE FROM fts_numbers", [])?;
        self.conn.execute("UPDATE classification_cache SET texto = '', texto_hash = ''", [])?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_database_lifecycle_and_fts() {
        let temp_dir = tempfile::tempdir().unwrap();
        let db_path = temp_dir.path().join("test_indexo.db");

        let mut db = IndexoDatabase::open(&db_path).unwrap();
        assert!(db.check_integrity().unwrap());

        let root_id = db.get_or_create_root("C:/Downloads", "Downloads").unwrap();
        assert!(root_id > 0);

        let file_id = db.upsert_file(root_id, "boleto_luz.pdf", "C:/Downloads/boleto_luz.pdf", 1024, 1700000000, Some("hash123"), "identificado").unwrap();
        assert!(file_id > 0);

        let fetched = db.get_file_by_id(file_id).unwrap().unwrap();
        assert_eq!(fetched.rel_path, "boleto_luz.pdf");
        assert_eq!(fetched.hash_sha256.as_deref(), Some("hash123"));

        // Test FTS search
        db.update_fts_content(
            "boleto_luz.pdf",
            "Conta de Luz",
            "AES Sul",
            "energia kwh",
            "Fatura de energia eletrica 350 kWh",
            "123.456.789-00",
            "",
            "23793381286008301352856000063307789012345678",
        ).unwrap();

        // Search by word
        let res_word = db.search_fts("energia").unwrap();
        assert_eq!(res_word.len(), 1);
        assert_eq!(res_word[0].rel_path, "boleto_luz.pdf");

        // Search by partial number (trigram)
        let res_num = db.search_fts("456.789").unwrap();
        assert_eq!(res_num.len(), 1);
        assert_eq!(res_num[0].rel_path, "boleto_luz.pdf");

        // Test deletion marking
        db.mark_for_deletion(file_id, true).unwrap();
        let marked = db.list_marked_for_deletion().unwrap();
        assert_eq!(marked.len(), 1);
        assert_eq!(marked[0].id, file_id);

        db.mark_for_deletion(file_id, false).unwrap();
        let unmark = db.list_marked_for_deletion().unwrap();
        assert_eq!(unmark.len(), 0);
    }
}
