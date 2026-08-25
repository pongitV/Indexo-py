pub mod classification;
pub mod extraction;
pub mod indexing;
pub mod utils;

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::path::Path;

use crate::classification::engine::{ClassificationKernel, RuleDefinition};
use crate::extraction::image::extract_image_exif;
use crate::extraction::text::read_text_file;
use crate::indexing::database::IndexoDatabase;
use crate::indexing::hashing::calculate_sha256;
use crate::indexing::sanitize::{resolve_collision, sanitize_filename};
use crate::indexing::scanner::scan_directory;
use crate::utils::path_resolver::validate_caminho_fisico;

#[pyfunction]
fn py_sanitize_filename(name: &str) -> String {
    sanitize_filename(name)
}

#[pyfunction]
fn py_resolve_collision(dest_dir: &str, desired_name: &str) -> String {
    let dest_path = Path::new(dest_dir);
    let resolved = resolve_collision(dest_path, desired_name);
    resolved.to_string_lossy().to_string()
}

#[pyfunction]
fn py_validate_caminho_fisico(caminho: &str) -> PyResult<String> {
    validate_caminho_fisico(caminho).map_err(|e| e.into())
}

#[pyfunction]
fn py_calculate_sha256(path: &str) -> PyResult<String> {
    calculate_sha256(Path::new(path)).map_err(|e| e.into())
}

#[pyfunction]
fn py_read_text_file(path: &str) -> PyResult<String> {
    read_text_file(Path::new(path)).map_err(|e| e.into())
}

#[pyfunction]
fn py_extract_image_exif(py: Python<'_>, path: &str) -> PyResult<PyObject> {
    let meta = extract_image_exif(Path::new(path)).map_err(|e| -> PyErr { e.into() })?;
    let dict = PyDict::new(py);
    dict.set_item("date_time_original", meta.date_time_original)?;
    dict.set_item("description", meta.description)?;
    dict.set_item("gps_latitude", meta.gps_latitude)?;
    dict.set_item("gps_longitude", meta.gps_longitude)?;
    dict.set_item("keywords", meta.keywords)?;
    Ok(dict.into())
}

#[pyfunction]
#[pyo3(signature = (path, include_hidden=false))]
fn py_scan_directory(py: Python<'_>, path: &str, include_hidden: bool) -> PyResult<PyObject> {
    let entries = scan_directory(Path::new(path), include_hidden, None).map_err(|e| -> PyErr { e.into() })?;
    let list = PyList::empty(py);
    for entry in entries {
        let dict = PyDict::new(py);
        dict.set_item("rel_path", entry.rel_path)?;
        dict.set_item("abs_path", entry.abs_path)?;
        dict.set_item("size", entry.size)?;
        dict.set_item("mtime", entry.mtime)?;
        dict.set_item("file_type", entry.file_type)?;
        dict.set_item("mime", entry.mime)?;
        dict.set_item("is_cloud_placeholder", entry.is_cloud_placeholder)?;
        dict.set_item("is_hidden", entry.is_hidden)?;
        list.append(dict)?;
    }
    Ok(list.into())
}

#[pyclass(unsendable)]
struct PyIndexoDatabase {
    inner: IndexoDatabase,
}

#[pymethods]
impl PyIndexoDatabase {
    #[staticmethod]
    fn open(db_path: &str) -> PyResult<Self> {
        let inner = IndexoDatabase::open(db_path).map_err(|e| -> PyErr { e.into() })?;
        Ok(Self { inner })
    }

    fn check_integrity(&self) -> PyResult<bool> {
        self.inner.check_integrity().map_err(|e| e.into())
    }

    fn get_or_create_root(&mut self, root_abs: &str, root_rel: &str) -> PyResult<i64> {
        self.inner.get_or_create_root(root_abs, root_rel).map_err(|e| e.into())
    }

    #[pyo3(signature = (root_id, rel_path, abs_path, size, mtime, hash=None, status="pendente"))]
    fn upsert_file(
        &mut self,
        root_id: i64,
        rel_path: &str,
        abs_path: &str,
        size: i64,
        mtime: i64,
        hash: Option<&str>,
        status: &str,
    ) -> PyResult<i64> {
        self.inner.upsert_file(root_id, rel_path, abs_path, size, mtime, hash, status).map_err(|e| e.into())
    }

    fn get_file_by_id(&self, py: Python<'_>, file_id: i64) -> PyResult<Option<PyObject>> {
        let file_opt = self.inner.get_file_by_id(file_id).map_err(|e| -> PyErr { e.into() })?;
        match file_opt {
            Some(f) => {
                let dict = PyDict::new(py);
                dict.set_item("id", f.id)?;
                dict.set_item("rel_path", f.rel_path)?;
                dict.set_item("abs_path", f.abs_path)?;
                dict.set_item("size", f.size)?;
                dict.set_item("mtime", f.mtime)?;
                dict.set_item("hash_sha256", f.hash_sha256)?;
                dict.set_item("folder_root_id", f.folder_root_id)?;
                dict.set_item("status", f.status)?;
                dict.set_item("origem_original", f.origem_original)?;
                dict.set_item("first_seen", f.first_seen)?;
                dict.set_item("last_seen", f.last_seen)?;
                dict.set_item("marked_for_deletion", f.marked_for_deletion)?;
                dict.set_item("marked_at", f.marked_at)?;
                Ok(Some(dict.into()))
            }
            None => Ok(None),
        }
    }

    fn mark_for_deletion(&mut self, file_id: i64, marked: bool) -> PyResult<()> {
        self.inner.mark_for_deletion(file_id, marked).map_err(|e| e.into())
    }

    fn list_marked_for_deletion(&self, py: Python<'_>) -> PyResult<PyObject> {
        let files = self.inner.list_marked_for_deletion().map_err(|e| -> PyErr { e.into() })?;
        let list = PyList::empty(py);
        for f in files {
            let dict = PyDict::new(py);
            dict.set_item("id", f.id)?;
            dict.set_item("rel_path", f.rel_path)?;
            dict.set_item("abs_path", f.abs_path)?;
            dict.set_item("size", f.size)?;
            dict.set_item("mtime", f.mtime)?;
            dict.set_item("hash_sha256", f.hash_sha256)?;
            dict.set_item("folder_root_id", f.folder_root_id)?;
            dict.set_item("status", f.status)?;
            dict.set_item("origem_original", f.origem_original)?;
            dict.set_item("first_seen", f.first_seen)?;
            dict.set_item("last_seen", f.last_seen)?;
            dict.set_item("marked_for_deletion", f.marked_for_deletion)?;
            dict.set_item("marked_at", f.marked_at)?;
            list.append(dict)?;
        }
        Ok(list.into())
    }

    fn delete_file_record(&mut self, file_id: i64) -> PyResult<()> {
        self.inner.delete_file_record(file_id).map_err(|e| e.into())
    }

    fn find_duplicates(&self, py: Python<'_>, root_id: i64) -> PyResult<PyObject> {
        let groups = self.inner.find_duplicates(root_id).map_err(|e| -> PyErr { e.into() })?;
        let py_groups = PyList::empty(py);
        for group in groups {
            let py_group = PyList::empty(py);
            for f in group {
                let dict = PyDict::new(py);
                dict.set_item("id", f.id)?;
                dict.set_item("rel_path", f.rel_path)?;
                dict.set_item("abs_path", f.abs_path)?;
                dict.set_item("size", f.size)?;
                dict.set_item("mtime", f.mtime)?;
                dict.set_item("hash_sha256", f.hash_sha256)?;
                dict.set_item("folder_root_id", f.folder_root_id)?;
                dict.set_item("status", f.status)?;
                dict.set_item("origem_original", f.origem_original)?;
                dict.set_item("marked_for_deletion", f.marked_for_deletion)?;
                dict.set_item("marked_at", f.marked_at)?;
                py_group.append(dict)?;
            }
            py_groups.append(py_group)?;
        }
        Ok(py_groups.into())
    }

    fn search_fts(&self, py: Python<'_>, query: &str) -> PyResult<PyObject> {
        let results = self.inner.search_fts(query).map_err(|e| -> PyErr { e.into() })?;
        let list = PyList::empty(py);
        for r in results {
            let dict = PyDict::new(py);
            dict.set_item("rel_path", r.rel_path)?;
            dict.set_item("tag", r.tag)?;
            dict.set_item("entidade", r.entidade)?;
            dict.set_item("snippet", r.snippet)?;
            dict.set_item("match_type", r.match_type)?;
            list.append(dict)?;
        }
        Ok(list.into())
    }

    #[pyo3(signature = (rel_path, tag="", entidade="", palavras_chave="", snippet="", cpf="", cnpj="", boleto=""))]
    fn update_fts_content(
        &mut self,
        rel_path: &str,
        tag: &str,
        entidade: &str,
        palavras_chave: &str,
        snippet: &str,
        cpf: &str,
        cnpj: &str,
        boleto: &str,
    ) -> PyResult<()> {
        self.inner
            .update_fts_content(rel_path, tag, entidade, palavras_chave, snippet, cpf, cnpj, boleto)
            .map_err(|e| e.into())
    }

    fn clear_content_privacy(&mut self) -> PyResult<()> {
        self.inner.clear_content_privacy().map_err(|e| e.into())
    }
}

#[pyclass]
struct PyClassificationKernel {
    inner: ClassificationKernel,
}

#[pymethods]
impl PyClassificationKernel {
    #[staticmethod]
    fn from_rules_json(rules_json: &str) -> PyResult<Self> {
        let rules: Vec<RuleDefinition> = serde_json::from_str(rules_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid rules JSON: {}", e)))?;
        let inner = ClassificationKernel::new(rules);
        Ok(Self { inner })
    }

    #[pyo3(signature = (text, file_ext, score_origem=0.0))]
    fn classify(&self, py: Python<'_>, text: &str, file_ext: &str, score_origem: f64) -> PyResult<Option<PyObject>> {
        let candidate = self.inner.classify(text, file_ext, score_origem);
        match candidate {
            Some(c) => {
                let dict = PyDict::new(py);
                dict.set_item("tag_id", c.tag_id)?;
                dict.set_item("nome", c.nome)?;
                dict.set_item("categoria", c.categoria)?;
                dict.set_item("subcategoria", c.subcategoria)?;
                dict.set_item("entidade", c.entidade)?;
                dict.set_item("caminho_fisico", c.caminho_fisico)?;
                dict.set_item("origem", c.origem)?;
                dict.set_item("confianca", c.confianca)?;
                dict.set_item("is_user_rule", c.is_user_rule)?;

                let scores = PyDict::new(py);
                scores.set_item("conteudo", c.scores.conteudo)?;
                scores.set_item("tipo", c.scores.tipo)?;
                scores.set_item("origem", c.scores.origem)?;
                dict.set_item("scores", scores)?;

                Ok(Some(dict.into()))
            }
            None => Ok(None),
        }
    }
}

#[pymodule]
fn indexo_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(py_sanitize_filename, m)?)?;
    m.add_function(wrap_pyfunction!(py_resolve_collision, m)?)?;
    m.add_function(wrap_pyfunction!(py_validate_caminho_fisico, m)?)?;
    m.add_function(wrap_pyfunction!(py_calculate_sha256, m)?)?;
    m.add_function(wrap_pyfunction!(py_read_text_file, m)?)?;
    m.add_function(wrap_pyfunction!(py_extract_image_exif, m)?)?;
    m.add_function(wrap_pyfunction!(py_scan_directory, m)?)?;
    m.add_class::<PyIndexoDatabase>()?;
    m.add_class::<PyClassificationKernel>()?;
    Ok(())
}
